"""Main application window and persistent navigation."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QStandardPaths
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from filemind.analyzer.metadata import FileMetadata
from filemind.gui.components import StatusBadge
from filemind.gui.icons import navigation_icon
from filemind.categorizer.classifier import ClassifiedFile
from filemind.duplicate_detector.detector import DuplicateProgress, DuplicateResult
from filemind.gui.history import JournalWorker
from filemind.organizer.organizer import MoveJournal
from filemind.gui.pages import (
    DashboardPage,
    DuplicateFinderPage,
    MyFilesPage,
    PAGE_FACTORIES,
)
from filemind.scanner.scanner import ScanIssue
from filemind.gui.workers import DirectoryScanWorker, DuplicateScanWorker


LOGGER = logging.getLogger(__name__)


PAGE_DESCRIPTIONS = {
    "Dashboard": "A clear view of your files and organization activity.",
    "My Files": "Browse the files discovered by your local scans.",
    "AI Organizer": "Review suggested destinations before anything changes.",
    "Duplicate Finder": "Find exact copies and review their storage impact.",
    "Activity History": "Review completed operations and safely undo moves.",
    "Settings": "Version and local processing details.",
}

PAGE_LABELS = {"Dashboard": "Overview", "AI Organizer": "Organizer", "Activity History": "History", "Settings": "About"}

NAV_ITEMS = (
    ("Dashboard", "⌂"),
    ("My Files", "▤"),
    ("AI Organizer", "✦"),
    ("Duplicate Finder", "⧉"),
    ("Activity History", "◷"),
    ("Settings", "⚙"),
)


class MainWindow(QMainWindow):
    def __init__(self, history_path=None) -> None:
        super().__init__()
        self.setWindowTitle("FileMind")
        self.setMinimumSize(980, 680)
        self.resize(1280, 820)

        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}
        self._stack = QStackedWidget()
        self._scan_worker: DirectoryScanWorker | None = None
        self._duplicate_worker: DuplicateScanWorker | None = None
        self._scan_files: list[FileMetadata] = []
        self._has_scan = False
        if history_path is None:
            location = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
            history_path = Path(location) / "moves.sqlite3"
        self._journal = MoveJournal(history_path)
        self._journal_worker = None
        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_content(), 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("LOCAL WORKSPACE   /   Ready")
        self._show_page("Dashboard")
        if self._journal.database.exists():
            self._run_journal("reconcile")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        layout = QHBoxLayout(sidebar)
        layout.setContentsMargins(24, 10, 24, 10)
        layout.setSpacing(4)
        brand = QLabel("FileMind")
        brand.setObjectName("BrandName")
        layout.addWidget(brand)
        layout.addSpacing(24)
        for title, _ in NAV_ITEMS:
            button = QPushButton(PAGE_LABELS.get(title, title))
            button.setIcon(navigation_icon(title))
            button.setIconSize(QSize(17, 17))
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, name=title: self._show_page(name))
            self._buttons[title] = button
            layout.addWidget(button)
        layout.addStretch()
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("ContentArea")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        page_container = QWidget()
        page_container.setObjectName("PageContainer")
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(20, 18, 20, 16)
        page_layout.setSpacing(0)

        for page_name, page_factory in PAGE_FACTORIES.items():
            page = page_factory()
            self._pages[page_name] = page
            self._stack.addWidget(page)
        dashboard = self._pages["Dashboard"]
        if isinstance(dashboard, DashboardPage):
            dashboard.scan_requested.connect(self._choose_directory)
            dashboard.downloads_requested.connect(self._scan_downloads)
            dashboard.category_requested.connect(self._browse_category)
            dashboard.review_requested.connect(lambda: self._show_page("AI Organizer"))
        duplicate_page = self._pages["Duplicate Finder"]
        if isinstance(duplicate_page, DuplicateFinderPage):
            duplicate_page.find_requested.connect(self._handle_duplicate_button)

        self._pages["AI Organizer"].apply_requested.connect(self._apply_moves)
        self._pages["Activity History"].undo_requested.connect(self._undo_moves)
        page_layout.addWidget(self._stack)
        scroll_area.setWidget(page_container)
        layout.addWidget(scroll_area, 1)
        return content

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        header.setMinimumHeight(72)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(30, 13, 30, 13)

        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(2)
        self._header_title = QLabel()
        self._header_title.setObjectName("HeaderTitle")
        self._header_subtitle = QLabel()
        self._header_subtitle.setObjectName("HeaderSubtitle")
        self._header_subtitle.setWordWrap(True)
        heading_layout.addWidget(self._header_title)
        heading_layout.addWidget(self._header_subtitle)
        layout.addLayout(heading_layout, 1)

        self._status_badge = StatusBadge("LOCAL ONLY")
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("ScanProgress")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedWidth(110)
        self._progress_bar.setMaximumHeight(8)
        self._progress_bar.hide()
        self._scan_button = QPushButton("Scan folder")
        self._scan_button.setObjectName("PrimaryButton")
        self._scan_button.clicked.connect(self._handle_scan_button)
        self._scan_button.setShortcut("Ctrl+O")
        self._scan_button.setToolTip("Choose a folder or cancel the current scan (Ctrl+O)")
        layout.addWidget(self._status_badge)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._scan_button)
        return header

    def _show_page(self, page_name: str) -> None:
        page = self._pages[page_name]
        self._stack.setCurrentWidget(page)
        self._header_title.setText(PAGE_LABELS.get(page_name, page_name))
        self._header_subtitle.setText(PAGE_DESCRIPTIONS[page_name])
        for name, button in self._buttons.items():
            button.setChecked(name == page_name)

    def _confirm_moves(self, verb, count):
        prompt = f"{verb} {count:,} selected file move(s)?"
        return QMessageBox.question(self, verb + " selected moves", prompt, QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No) == QMessageBox.Yes

    def _apply_moves(self):
        page = self._pages["AI Organizer"]
        selected = page.selected_proposals()
        if selected and self._confirm_moves("Apply", len(selected)):
            metadata = {item.metadata.path: item.metadata for item in page._files}
            self._run_journal("apply", page._directory, selected, metadata)

    def _undo_moves(self, ids):
        if ids and self._confirm_moves("Undo", len(ids)):
            self._run_journal("undo", ids)

    def _run_journal(self, action, *args):
        if self._journal_worker or self._scan_worker or self._duplicate_worker:
            return
        worker = JournalWorker(self._journal, action, args, self)
        self._journal_worker = worker
        self.centralWidget().setEnabled(False)
        self._set_status("CHECKING HISTORY" if action == "reconcile" else "PROCESSING MOVES", muted=True)
        worker.finished.connect(self._journal_finished)
        worker.start()

    def _journal_finished(self):
        worker = self._journal_worker
        self._journal_worker = None
        self.centralWidget().setEnabled(True)
        self._set_status("LOCAL ONLY", muted=False)
        history = self._pages["Activity History"]
        if worker.error:
            QMessageBox.warning(self, "Activity History", worker.error)
        else:
            history.show_rows(worker.rows)
        if worker.action != "reconcile":
            self._show_page("Activity History")
            directory = self._pages["AI Organizer"]._directory
            if directory is not None:
                self._start_scan(directory)
        worker.deleteLater()

    def _browse_category(self, category):
        page = self._pages["My Files"]
        page._search.clear()
        page._category_filter.setCurrentText(category)
        self._show_page("My Files")

    def _scan_downloads(self):
        location = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        if location and Path(location).is_dir():
            self._start_scan(Path(location))
        else:
            self._choose_directory()

    def _choose_directory(self) -> None:
        if self._scan_worker is not None or self._duplicate_worker is not None:
            return

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Choose a folder to scan",
        )
        if selected_directory:
            self._start_scan(Path(selected_directory))

    def _handle_scan_button(self) -> None:
        if self._duplicate_worker is not None:
            return
        if self._scan_worker is not None:
            if self._scan_worker.isRunning():
                self._scan_worker.cancel()
                self._scan_button.setText("Cancelling...")
                self._scan_button.setEnabled(False)
                self._set_status("CANCELLING", muted=True)
            return
        self._choose_directory()

    def _start_scan(self, directory: Path) -> None:
        if self._duplicate_worker is not None or self._scan_worker is not None:
            return
        worker = DirectoryScanWorker(directory)
        worker.progress.connect(self._on_scan_progress)
        worker.completed.connect(self._on_scan_completed)
        worker.failed.connect(self._on_scan_failed)
        worker.cancelled.connect(self._on_scan_cancelled)
        worker.finished.connect(self._on_scan_worker_finished)
        self._scan_worker = worker
        self._pages["AI Organizer"].setEnabled(False)
        self._pages["Activity History"].setEnabled(False)
        self._scan_button.setText("Cancel scan")
        self._scan_button.setEnabled(True)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.show()
        self._set_status("SCANNING", muted=True)

        dashboard = self._pages["Dashboard"]
        if isinstance(dashboard, DashboardPage):
            dashboard.set_scan_running(directory)
        worker.start()

    def _on_scan_progress(self, stage: str, current: int, total: int) -> None:
        self.statusBar().showMessage(
            f"{stage.upper()}   /   {current:,}" + (f" of {total:,} files" if total else " files discovered")
        )
        if stage == "Analyzing" and total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
            self._set_status("ANALYZING", muted=True)
        else:
            self._progress_bar.setRange(0, 0)
            self._set_status("SCANNING", muted=True)

    def _on_scan_completed(
        self,
        directory: Path,
        files: list[ClassifiedFile],
        issues: tuple[ScanIssue, ...],
    ) -> None:
        dashboard = self._pages["Dashboard"]
        if isinstance(dashboard, DashboardPage):
            dashboard.set_scan_result(directory, files, len(issues))

        files_page = self._pages["My Files"]
        if isinstance(files_page, MyFilesPage):
            files_page.set_scan_result(directory, files)
        self._pages["AI Organizer"].set_scan_result(directory, files)
        self._scan_files = [item.metadata for item in files]
        self._has_scan = True
        duplicate_page = self._pages["Duplicate Finder"]
        if isinstance(duplicate_page, DuplicateFinderPage):
            duplicate_page.set_scan_available(True)
        dashboard._metric_cards[2].set_value("—", "Ready to check")
        analysis_errors = sum(item.metadata.analysis_error is not None for item in files)
        if issues or analysis_errors:
            for issue in issues:
                LOGGER.warning("Scan issue in %s: %s", issue.path, issue.message)
            self._set_status("SCAN WARNINGS", muted=True)
            QMessageBox.warning(
                self,
                "Scan completed with warnings",
                f"Found {len(files)} files. {len(issues)} filesystem issue(s) "
                f"and {analysis_errors} analysis warning(s) occurred. "
                "Select a file to see its analysis details.",
            )
        else:
            self._set_status("LOCAL ONLY", muted=False)

    def _on_scan_failed(self, directory: Path, message: str) -> None:
        dashboard = self._pages["Dashboard"]
        if isinstance(dashboard, DashboardPage):
            dashboard.set_scan_failed(directory)
        self._set_status("SCAN FAILED", muted=True)
        QMessageBox.warning(
            self,
            "Scan failed",
            f"Could not scan this folder:\n{directory}\n\n{message}",
        )

    def _on_scan_cancelled(self, directory: Path) -> None:
        dashboard = self._pages["Dashboard"]
        if isinstance(dashboard, DashboardPage):
            dashboard.set_scan_cancelled(directory)
        self._set_status("SCAN CANCELLED", muted=True)

    def _handle_duplicate_button(self) -> None:
        worker = self._duplicate_worker
        if worker is not None:
            if worker.isRunning():
                worker.cancel()
                duplicate_page = self._pages["Duplicate Finder"]
                if isinstance(duplicate_page, DuplicateFinderPage):
                    duplicate_page.set_cancelling()
                self._set_status("CANCELLING", muted=True)
            return
        self._start_duplicate_check()

    def _start_duplicate_check(self) -> None:
        if self._scan_worker is not None or self._duplicate_worker is not None:
            return
        if not self._has_scan:
            return

        worker = DuplicateScanWorker(self._scan_files)
        worker.progress.connect(self._on_duplicate_progress)
        worker.completed.connect(self._on_duplicate_completed)
        worker.failed.connect(self._on_duplicate_failed)
        worker.finished.connect(self._on_duplicate_worker_finished)
        self._duplicate_worker = worker
        self._scan_button.setEnabled(False)
        self._pages["AI Organizer"].setEnabled(False)
        self._pages["Activity History"].setEnabled(False)
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._set_status("HASHING", muted=True)

        duplicate_page = self._pages["Duplicate Finder"]
        if isinstance(duplicate_page, DuplicateFinderPage):
            duplicate_page.set_running()
        worker.start()

    def _on_duplicate_progress(self, progress: DuplicateProgress) -> None:
        duplicate_page = self._pages["Duplicate Finder"]
        if isinstance(duplicate_page, DuplicateFinderPage):
            duplicate_page.set_progress(progress)
        if progress.total_bytes:
            value = int(progress.bytes_hashed * 1000 / progress.total_bytes)
        elif progress.total_files:
            value = int(progress.files_processed * 1000 / progress.total_files)
        else:
            value = 0
        self._progress_bar.setValue(min(value, 1000))
        self._set_status("HASHING", muted=True)

    def _on_duplicate_completed(self, result: DuplicateResult) -> None:
        duplicate_page = self._pages["Duplicate Finder"]
        if isinstance(duplicate_page, DuplicateFinderPage):
            if result.cancelled:
                duplicate_page.set_cancelled()
            else:
                duplicate_page.set_result(result)

        if not result.cancelled:
            dashboard = self._pages["Dashboard"]
            dashboard._metric_cards[2].set_value(str(len(result.groups)), "Exact content matches")
        if result.cancelled:
            self._set_status("CHECK CANCELLED", muted=True)
            return

        if result.issues:
            for issue in result.issues:
                LOGGER.warning("Duplicate check skipped %s: %s", issue.path, issue.message)
            self._set_status("CHECK WARNINGS", muted=True)
            QMessageBox.warning(
                self,
                "Duplicate check completed with warnings",
                f"Found {len(result.groups)} duplicate group(s). "
                f"{len(result.issues)} file issue(s) occurred.",
            )
        else:
            self._set_status("LOCAL ONLY", muted=False)

    def _on_duplicate_failed(self, message: str) -> None:
        page = self._pages["Duplicate Finder"]
        if isinstance(page, DuplicateFinderPage):
            page.set_cancelled()
            page._summary.setText("Check failed; previous results were kept.")
        self._set_status("CHECK FAILED", muted=True)
        QMessageBox.warning(self, "Duplicate check failed", message)

    def _on_duplicate_worker_finished(self) -> None:
        worker = self._duplicate_worker
        self._pages["AI Organizer"].setEnabled(True)
        self._pages["Activity History"].setEnabled(True)
        self._duplicate_worker = None
        self._scan_button.setEnabled(True)
        self._progress_bar.hide()
        if worker is not None:
            worker.deleteLater()

    def _on_scan_worker_finished(self) -> None:
        worker = self._scan_worker
        self._pages["AI Organizer"].setEnabled(True)
        self._pages["Activity History"].setEnabled(True)
        self._scan_worker = None
        self._scan_button.setEnabled(True)
        self._scan_button.setText("Scan folder")
        self._progress_bar.hide()
        if worker is not None:
            worker.deleteLater()

    def _set_status(self, text: str, muted: bool) -> None:
        self.statusBar().showMessage(f"LOCAL WORKSPACE   /   {text}")
        self._status_badge.setText(text)
        self._status_badge.setObjectName(
            "StatusBadgeMuted" if muted else "StatusBadge"
        )
        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._journal_worker is not None:
            event.ignore()
            self.statusBar().showMessage("Finishing file operations before closing")
            return
        workers = [
            worker
            for worker in (self._scan_worker, self._duplicate_worker)
            if worker is not None
        ]
        files_page = self._pages["My Files"]
        files_page._pending_preview = None
        files_page._closing = True
        if files_page._preview_worker is not None:
            workers.append(files_page._preview_worker)
        workers.extend(self._pages["AI Organizer"].workers)
        for worker in workers:
            if worker.isRunning() and hasattr(worker, "cancel"):
                worker.cancel()
        for worker in workers:
            if worker.isRunning() and not worker.wait(5000):
                LOGGER.warning("Background worker did not stop promptly during close")
                event.ignore()
                files_page._closing = False
                return
        event.accept()
