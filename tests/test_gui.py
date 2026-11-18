import os
from pathlib import Path
from threading import Event
from collections.abc import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from shiboken6 import isValid
from PySide6.QtCore import QEventLoop, QThread, QTimer, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from filemind.analyzer.metadata import analyze_file
from filemind.categorizer.classifier import ClassifiedFile, RuleBasedClassifier
from filemind.gui.pages import DashboardPage, DuplicateFinderPage, MyFilesPage
from filemind.gui.window import MainWindow, NAV_ITEMS
from filemind.gui.workers import DirectoryScanWorker
from filemind.scanner.scanner import ScanProgress, ScanResult


def test_scan_worker_reports_unexpected_analysis_failure(tmp_path, monkeypatch):
    (tmp_path / "notes.txt").write_text("notes")
    def fail(*args, **kwargs):
        raise RuntimeError("analysis failed")
    monkeypatch.setattr("filemind.gui.workers.analyze_file", fail)
    worker = DirectoryScanWorker(tmp_path)
    failed = QSignalSpy(worker.failed)
    worker.run()
    assert failed.count() == 1
    assert failed.at(0)[1] == "analysis failed"


def test_duplicate_worker_reports_unexpected_failure(tmp_path, monkeypatch):
    from filemind.gui.workers import DuplicateScanWorker
    def fail(*args, **kwargs):
        raise RuntimeError("hashing failed")
    monkeypatch.setattr("filemind.gui.workers.find_duplicates", fail)
    worker = DuplicateScanWorker([])
    failed = QSignalSpy(worker.failed)
    worker.run()
    assert failed.count() == 1
    assert failed.at(0)[0] == "hashing failed"


def test_sorted_filtered_selection_previews_the_correct_file(application, tmp_path):
    window = MainWindow()
    page = window._pages["My Files"]
    files = []
    for name, content in (("small.txt", "tiny"), ("large.py", "print('large content')")):
        path = tmp_path / name
        path.write_text(content)
        metadata = analyze_file(path, extract_content=False)
        files.append(ClassifiedFile(metadata, RuleBasedClassifier().classify(metadata)))
    page.set_scan_result(tmp_path, files)
    page._table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
    page._table.setCurrentIndex(page._proxy.index(0, 0))
    # Drain the active request and the latest queued selection.
    for _ in range(3):
        if page._preview_worker is not None:
            _wait_for_worker(application, page._preview_worker)
    assert page._proxy.index(0, 0).data() == "large.py"
    assert "large content" in page._preview.toPlainText()
    page._category_filter.setCurrentText("Documents")
    for _ in range(3):
        if page._preview_worker is not None:
            _wait_for_worker(application, page._preview_worker)
    assert page._proxy.rowCount() == 1
    assert "tiny" in page._preview.toPlainText()
    window.close()


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
    assert not isValid(worker) or not worker.isRunning(), "Background task did not finish before the timeout"
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
    assert files_page._proxy.rowCount() == 2
    assert files_page._proxy.index(0, 0).data() == "meeting-notes.txt"
    assert files_page._proxy.index(0, 4).data() == "Documents"
    assert files_page._proxy.index(1, 4).data() == "Code"
    assert dashboard._metric_cards[0].value_widget.text() == "2"
    assert dashboard._metric_cards[3].value_widget.text() == "2"
    assert dashboard._distribution_layout.count() == 2
    assert {dashboard._distribution_layout.itemAt(i).widget().layout().itemAt(0).widget().text()
            for i in range(2)} == {"Documents", "Code"}
    if files_page._preview_worker is not None:
        _wait_for_worker(application, files_page._preview_worker)
    assert "unchanged" in files_page._preview.toPlainText()
    assert window._status_badge.text() == "LOCAL ONLY"
    assert file_path.read_text(encoding="utf-8") == "unchanged"

    files_page._search.setText("not found")
    QTest.qWait(160)
    assert files_page._proxy.rowCount() == 0
    files_page._search.setText("meeting")
    QTest.qWait(160)
    assert files_page._proxy.rowCount() == 1
    files_page._search.clear()
    files_page._category_filter.setCurrentText("Code")
    assert files_page._proxy.rowCount() == 1
    assert files_page._proxy.index(0, 4).data() == "Code"
    window.close()


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
    assert window._pages["Dashboard"]._metric_cards[2].value_widget.text() == "1"
    window.close()


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
    assert files_page._proxy.rowCount() == 1
    assert files_page._proxy.index(0, 0).data() == "previous.txt"


def test_scan_worker_reports_filesystem_errors(tmp_path: Path) -> None:
    directory = tmp_path / "missing"
    worker = DirectoryScanWorker(directory)
    failures = QSignalSpy(worker.failed)

    worker.run()

    assert failures.count() == 1
    assert failures.at(0)[0] == directory
    assert "Directory not found" in failures.at(0)[1]


@pytest.mark.parametrize("change", ["size", "mtime", "replacement", "missing", "unreadable"])
def test_preview_refreshes_after_external_change(application, tmp_path, monkeypatch, change):
    original = tmp_path / "a.txt"
    other = tmp_path / "b.txt"
    original.write_text("old content")
    other.write_text("other")
    files = []
    for path in (original, other):
        metadata = analyze_file(path, extract_content=False)
        files.append(ClassifiedFile(metadata, RuleBasedClassifier().classify(metadata)))
    window = MainWindow()
    page = window._pages["My Files"]

    def drain():
        for _ in range(5):
            if page._preview_worker is not None:
                _wait_for_worker(application, page._preview_worker)

    try:
        page.set_scan_result(tmp_path, files)
        drain()
        assert "old content" in page._preview.toPlainText()
        old_stat = original.stat()
        if change == "size":
            original.write_text("updated longer content")
            os.utime(original, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
        elif change == "mtime":
            original.write_text("new content")
            os.utime(original, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns + 1_000_000))
        elif change == "replacement":
            replacement = tmp_path / "replacement"
            replacement.write_text("new content")
            os.utime(replacement, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            replacement.replace(original)
        elif change == "missing":
            original.unlink()
        else:
            real_open = Path.open
            def denied(path, *args, **kwargs):
                if path == original:
                    raise PermissionError("Access denied")
                return real_open(path, *args, **kwargs)
            monkeypatch.setattr(Path, "open", denied)
        page._table.setCurrentIndex(page._proxy.index(1, 0))
        drain()
        page._table.setCurrentIndex(page._proxy.index(0, 0))
        drain()
        text = page._preview.toPlainText()
        assert "old content" not in text
        assert {"size": "updated longer content", "mtime": "new content", "replacement": "new content",
                "missing": "Could not read", "unreadable": "Could not read"}[change] in text
    finally:
        window.close()


def test_organizer_replaces_plan_after_completed_scan(application, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "report.txt").write_text("report")
    window = MainWindow()
    try:
        page = window._pages["AI Organizer"]
        window._start_scan(first)
        _wait_for_worker(application, window._scan_worker)
        wait_plan(application, page)
        assert page.model.rowCount() == 1
        row = lambda col: page.model.index(0, col).data()
        assert row(0) == str(first / "report.txt")
        assert row(1) == str(first / "Organized" / "Documents" / "report.txt")
        assert row(3) == "No conflict detected"
        assert not (first / "Organized").exists()
        window._start_scan(second)
        _wait_for_worker(application, window._scan_worker)
        wait_plan(application, page)
        assert page.model.rowCount() == 0
        assert page.model.rows == ()
    finally:
        window.close()


def test_dashboard_distribution_details_refresh(application, tmp_path):
    from dataclasses import replace

    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    code = tmp_path / "script.py"
    first.write_text("abc")
    second.write_text("longer")
    code.write_text("pass")
    classifier = RuleBasedClassifier()
    files = []
    for path in (first, second, code):
        metadata = analyze_file(path, extract_content=False)
        if path == second:
            metadata = replace(metadata, size_bytes=None)
        files.append(ClassifiedFile(metadata, classifier.classify(metadata)))
    dashboard = DashboardPage()
    dashboard.set_scan_result(tmp_path, files, 0)
    assert dashboard._category_chart._counts == {"Documents": 2, "Code": 1}
    documents = dashboard._distribution_layout.itemAt(0).widget()
    details = documents.layout().itemAt(1).widget().text()
    assert "2 files" in details
    assert "67%" in details
    assert "1/2 sizes available" in details
    assert ".txt (2)" in details
    dashboard.set_scan_result(tmp_path, [], 0)
    assert dashboard._category_chart._counts == {}
    assert "No files found" in dashboard._distribution_layout.itemAt(0).widget().text()


def test_category_chart_tooltip_identifies_hovered_segment(application, monkeypatch):
    from PySide6.QtCore import QPoint, QEvent
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QToolTip
    from filemind.gui.pages import CategoryChart

    chart = CategoryChart()
    chart.resize(200, 200)
    chart.set_counts([("Documents", 3), ("Images", 1)])
    messages = []
    monkeypatch.setattr(QToolTip, "showText", lambda position, text, widget: messages.append(text))
    # The ring begins at the top and proceeds clockwise.
    for point in (QPoint(177, 100), QPoint(23, 100)):
        QApplication.sendEvent(chart, QHelpEvent(QEvent.Type.ToolTip, point, point))
    assert messages == ["Documents: 3 files (75%)", "Images: 1 files (25%)"]
    QApplication.sendEvent(chart, QHelpEvent(QEvent.Type.ToolTip, QPoint(100, 100), QPoint(100, 100)))
    assert len(messages) == 2
    chart.set_counts([])
    QApplication.sendEvent(chart, QHelpEvent(QEvent.Type.ToolTip, QPoint(177, 100), QPoint(177, 100)))
    assert len(messages) == 2


def test_organizer_selection_and_custom_folder(application, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    path = tmp_path / "report.txt"
    path.write_text("report")
    metadata = analyze_file(path, extract_content=False)
    window = MainWindow()
    page = window._pages["AI Organizer"]
    page.set_scan_result(tmp_path, [ClassifiedFile(metadata, RuleBasedClassifier().classify(metadata))])
    wait_plan(application, page)
    assert len(page.selected_proposals()) == 1
    page.model.setData(page.model.index(0, 0), Qt.Unchecked, Qt.CheckStateRole)
    assert not page.selected_proposals()
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args, **kwargs: ("Documents", True))
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Paperwork", True))
    page._customize_folder()
    wait_plan(application, page)
    assert not page.selected_proposals()
    assert page.model.rows[0].destination == tmp_path / "Organized" / "Paperwork" / "report.txt"
    assert not (tmp_path / "Organized").exists()


def wait_plan(application, page):
    while page.workers:
        worker = next(iter(page.workers))
        _wait_for_worker(application, worker)
    application.processEvents()


def test_old_plan_completion_cannot_replace_new_scan(application, tmp_path):
    from filemind.gui.pages import OrganizerPage

    page = OrganizerPage()
    page.set_scan_result(tmp_path, [])
    old_generation = page.generation
    page.set_scan_result(tmp_path, [])
    wait_plan(application, page)
    page._accept_plan(old_generation, ("obsolete",), "")
    assert page.model.rowCount() == 0


def test_apply_and_undo_through_reopened_history(application, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from test_moves import user_file

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    folder = tmp_path / "Downloads"
    folder.mkdir()
    for name in ("a.txt", "b.txt"):
        user_file(folder / name, name)
    history_path = tmp_path / "history.db"
    window = MainWindow(history_path)
    window._start_scan(folder)
    _wait_for_worker(application, window._scan_worker)
    page = window._pages["AI Organizer"]
    wait_plan(application, page)
    page.model.setData(page.model.index(1, 0), Qt.Unchecked, Qt.CheckStateRole)
    prompts = []
    responses = iter([QMessageBox.No, QMessageBox.Yes, QMessageBox.Yes])

    def confirm(parent, title, prompt, *args):
        prompts.append(prompt)
        return next(responses)
    monkeypatch.setattr(QMessageBox, "question", confirm)
    page.apply_button.click()
    assert not history_path.exists() and not (folder / "Organized").exists()
    page.apply_button.click()
    _wait_for_worker(application, window._journal_worker)
    if window._scan_worker is not None:
        _wait_for_worker(application, window._scan_worker)
    wait_plan(application, page)
    assert (folder / "Organized/Documents/a.txt").read_text() == "a.txt"
    assert (folder / "b.txt").read_text() == "b.txt"
    assert window.close()
    reopened = MainWindow(history_path)
    _wait_for_worker(application, reopened._journal_worker)
    reopened._buttons["Activity History"].click()
    history = reopened._pages["Activity History"]
    history.table.selectRow(0)
    history.button.click()
    _wait_for_worker(application, reopened._journal_worker)
    assert history.model.rows[0]["status"] == "undone"
    assert (folder / "a.txt").read_text() == "a.txt"
    assert not (folder / "Organized/Documents/a.txt").exists()
    assert all("1 selected file" in prompt for prompt in prompts)
    assert len(prompts) == 3
    assert reopened.close()
