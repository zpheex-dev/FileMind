import os
from pathlib import Path
from threading import Event
from collections.abc import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from filemind.analyzer.metadata import analyze_file
from filemind.categorizer.classifier import ClassifiedFile, RuleBasedClassifier
from filemind.gui.pages import DashboardPage, DuplicateFinderPage, MyFilesPage
from filemind.gui.window import MainWindow, NAV_ITEMS
from filemind.gui.workers import DirectoryScanWorker
from filemind.scanner.scanner import ScanProgress, ScanResult


@pytest.fixture(scope="session")
def application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _wait_for_worker(application: QApplication, worker: QThread) -> None:
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    worker.finished.connect(loop.quit)
    if not worker.isFinished():
        timeout.start(5000)
        loop.exec()
    timeout.stop()
    application.processEvents()


def test_window_builds_every_navigation_page(application: QApplication) -> None:
    window = MainWindow()

    assert set(window._pages) == {name for name, _ in NAV_ITEMS}
    assert window._stack.currentWidget() is window._pages["Dashboard"]
    assert len(window._buttons) == len(NAV_ITEMS)


def test_navigation_changes_the_visible_page(application: QApplication) -> None:
    window = MainWindow()
    target_page = "Duplicate Finder"

    window._buttons[target_page].click()

    assert window._stack.currentWidget() is window._pages[target_page]
    assert window._header_title.text() == target_page


def test_scan_updates_dashboard_and_file_explorer(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "meeting-notes.txt"
    file_path.write_text("unchanged", encoding="utf-8")
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()
    (nested_directory / "nested.py").write_text(
        "print('nested')",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "filemind.gui.window.QFileDialog.getExistingDirectory",
        lambda *args: str(tmp_path),
    )
    window = MainWindow()
    window._scan_button.click()
    worker = window._scan_worker
    assert worker is not None

    _wait_for_worker(application, worker)

    assert window._scan_worker is None
    assert window._scan_button.isEnabled()
    assert window._scan_button.text() == "Scan folder"
    assert not window._progress_bar.isVisible()
    files_page = window._pages["My Files"]
    dashboard = window._pages["Dashboard"]
    assert isinstance(files_page, MyFilesPage)
    assert isinstance(dashboard, DashboardPage)
    assert files_page._table.rowCount() == 2
    assert files_page._table.item(0, 0).text() == "meeting-notes.txt"
    assert files_page._table.item(0, 4).text() == "Documents"
    assert files_page._table.item(1, 4).text() == "Code"
    assert dashboard._metric_cards[0].value_widget.text() == "2"
    assert dashboard._metric_cards[3].value_widget.text() == "2"
    assert "Documents: 1" in dashboard._scan_empty_state.description_label.text()
    assert "unchanged" in files_page._preview.toPlainText()
    assert file_path.read_text(encoding="utf-8") == "unchanged"

    files_page._search.setText("not found")
    assert files_page._table.isRowHidden(0)
    files_page._search.setText("meeting")
    assert not files_page._table.isRowHidden(0)
    files_page._search.clear()
    files_page._category_filter.setCurrentText("Code")
    assert files_page._table.isRowHidden(0)
    assert not files_page._table.isRowHidden(1)


def test_duplicate_finder_uses_scan_results_without_changing_files(
    application: QApplication,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    content = b"identical local file contents"
    first.write_bytes(content)
    second.write_bytes(content)
    window = MainWindow()

    window._start_scan(tmp_path)
    scan_worker = window._scan_worker
    assert scan_worker is not None
    _wait_for_worker(application, scan_worker)
    assert window._has_scan

    duplicate_page = window._pages["Duplicate Finder"]
    assert isinstance(duplicate_page, DuplicateFinderPage)
    assert duplicate_page._find_button.isEnabled()
    duplicate_page._find_button.click()
    duplicate_worker = window._duplicate_worker
    assert duplicate_worker is not None
    _wait_for_worker(application, duplicate_worker)

    assert window._duplicate_worker is None
    assert duplicate_page._tree.topLevelItemCount() == 1
    group = duplicate_page._tree.topLevelItem(0)
    assert group.childCount() == 2
    assert "1 groups" in duplicate_page._summary.text()
    assert first.read_bytes() == second.read_bytes() == content


def test_scan_can_be_cancelled_from_the_header(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    previous_file = tmp_path / "previous.txt"
    previous_file.write_text("previous scan", encoding="utf-8")

    def wait_for_cancellation(
        directory: Path,
        progress_callback: Callable[[ScanProgress], None],
        cancellation_event: Event,
    ) -> ScanResult:
        started.set()
        progress_callback(ScanProgress(0, 0))
        cancellation_event.wait(2)
        return ScanResult(directory, (), (), 1, cancellation_event.is_set())

    monkeypatch.setattr(
        "filemind.gui.workers.scan_directory",
        wait_for_cancellation,
    )
    window = MainWindow()
    files_page = window._pages["My Files"]
    assert isinstance(files_page, MyFilesPage)
    previous_metadata = analyze_file(previous_file)
    previous_classification = RuleBasedClassifier().classify(previous_metadata)
    files_page.set_scan_result(
        tmp_path,
        [ClassifiedFile(previous_metadata, previous_classification)],
    )
    window._start_scan(tmp_path)
    worker = window._scan_worker
    assert worker is not None
    assert started.wait(1)

    window._handle_scan_button()
    _wait_for_worker(application, worker)

    assert window._scan_worker is None
    assert window._status_badge.text() == "SCAN CANCELLED"
    assert window._scan_button.isEnabled()
    assert not window._progress_bar.isVisible()
    assert files_page._table.rowCount() == 1
    assert files_page._table.item(0, 0).text() == "previous.txt"


def test_scan_worker_reports_filesystem_errors(tmp_path: Path) -> None:
    directory = tmp_path / "missing"
    worker = DirectoryScanWorker(directory)
    failures = QSignalSpy(worker.failed)

    worker.run()

    assert failures.count() == 1
    assert failures.at(0)[0] == directory
    assert "Directory not found" in failures.at(0)[1]
