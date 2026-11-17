"""Background tasks used by the desktop interface."""

import logging
from pathlib import Path
from threading import Event
from time import monotonic

from PySide6.QtCore import QThread, Signal

from filemind.analyzer.metadata import FileMetadata, analyze_file
from filemind.categorizer.classifier import (
    ClassifiedFile,
    Classifier,
    RuleBasedClassifier,
)
from filemind.duplicate_detector.detector import (
    find_duplicates,
)
from filemind.scanner.scanner import ScanProgress, scan_directory


LOGGER = logging.getLogger(__name__)


class DirectoryScanWorker(QThread):
    """Scan and analyze a directory without blocking the GUI thread."""

    progress = Signal(str, int, int)
    completed = Signal(object, object, object)
    failed = Signal(object, str)
    cancelled = Signal(object)

    def __init__(
        self,
        directory: Path,
        classifier: Classifier | None = None,
    ) -> None:
        super().__init__()
        self.directory = directory
        self._classifier = (
            RuleBasedClassifier() if classifier is None else classifier
        )
        self._cancellation_event = Event()
        self._last_progress = 0.0

    def cancel(self) -> None:
        self._cancellation_event.set()

    def run(self) -> None:
        try:
            self._run_scan()
        except Exception as error:
            LOGGER.exception("Scan failed")
            self.failed.emit(self.directory, str(error))

    def _run_scan(self) -> None:
        try:
            scan_result = scan_directory(
                self.directory,
                progress_callback=self._report_scan_progress,
                cancellation_event=self._cancellation_event,
            )
        except OSError as error:
            LOGGER.warning("Could not scan directory %s: %s", self.directory, error)
            self.failed.emit(self.directory, str(error))
            return

        if scan_result.cancelled or self._cancellation_event.is_set():
            self.cancelled.emit(self.directory)
            return

        total_files = len(scan_result.files)
        analyses: list[ClassifiedFile] = []
        last_analysis_progress = monotonic()
        self.progress.emit("Analyzing", 0, total_files)
        for index, file_path in enumerate(scan_result.files, start=1):
            if self._cancellation_event.is_set():
                self.cancelled.emit(self.directory)
                return

            metadata = analyze_file(file_path, extract_content=False)
            classification = self._classifier.classify(metadata)
            analyses.append(ClassifiedFile(metadata, classification))
            if monotonic() - last_analysis_progress >= 0.05 or index == total_files:
                self.progress.emit("Analyzing", index, total_files)
                last_analysis_progress = monotonic()

        if self._cancellation_event.is_set():
            self.cancelled.emit(self.directory)
            return
        self.completed.emit(self.directory, analyses, scan_result.issues)

    def _report_scan_progress(self, progress: ScanProgress) -> None:
        now = monotonic()
        if now - self._last_progress >= 0.05:
            self.progress.emit("Scanning", progress.files_found, 0)
            self._last_progress = now


class DuplicateScanWorker(QThread):
    """Hash duplicate candidates in the background."""

    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, files: list[FileMetadata]) -> None:
        super().__init__()
        self._files = tuple(files)
        self._cancellation_event = Event()

    def cancel(self) -> None:
        self._cancellation_event.set()

    def run(self) -> None:
        try:
            result = find_duplicates(
                self._files,
                progress_callback=self.progress.emit,
                cancellation_event=self._cancellation_event,
            )
            self.completed.emit(result)
        except Exception as error:
            LOGGER.exception("Duplicate check failed")
            self.failed.emit(str(error))


class PreviewWorker(QThread):
    completed = Signal(object)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            self.completed.emit(analyze_file(self.path))
        except Exception:
            LOGGER.exception("Preview failed for %s", self.path)
            self.completed.emit(None)
