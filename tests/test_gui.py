import os
from pathlib import Path
from threading import Event
from collections.abc import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from shiboken6 import isValid
from PySide6.QtCore import QAbstractAnimation, QEventLoop, QSettings, QThread, QTimer, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QPushButton

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
    page._table.setCurrentIndex(page._model.index(1, 0))
    assert page._table.currentIndex().data() == "small.txt"
    page._table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
    assert page._table.currentIndex().data() == "small.txt"
    page._table.setCurrentIndex(page._model.index(0, 0))
    # Drain the active request and the latest queued selection.
    for _ in range(3):
        if page._preview_worker is not None:
            _wait_for_worker(application, page._preview_worker)
    assert page._model.index(0, 0).data() == "large.py"
    assert "large content" in page._preview.toPlainText()
    page._category_filter.setCurrentText("Documents")
    for _ in range(3):
        if page._preview_worker is not None:
            _wait_for_worker(application, page._preview_worker)
    assert page._model.rowCount() == 1
    assert "tiny" in page._preview.toPlainText()
    window.close()


@pytest.fixture
def application():
    from PySide6.QtCore import QCoreApplication, QEvent
    app = QApplication.instance() or QApplication([])
    yield app
    for widget in app.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.close()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


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
    assert window._header_title.text() == "Duplicates"


def test_reduce_motion_stops_transitions_and_keeps_scan_progress(application, tmp_path):
    window = MainWindow(tmp_path / "history.db")
    window._appearance = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    preference = window._pages["Settings"].reduce_motion
    preference.setChecked(False)
    window.show()
    application.processEvents()

    progress = window._progress_bar
    progress.begin()
    assert progress._sweep.state() == QAbstractAnimation.State.Running
    window._buttons["My Files"].click()
    window._buttons["Settings"].click()
    assert window._stack.currentWidget() is window._pages["Settings"]
    assert window._page_transition.isVisible()

    preference.setChecked(True)
    assert progress.isVisible()
    assert progress._sweep.state() == QAbstractAnimation.State.Stopped
    assert not window._page_transition.isVisible()
    progress.report(3, 12)
    assert progress.value() == 3
    preference.setChecked(False)
    assert progress._fill.currentValue() == 0.25
    progress.hide()


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
    assert window._scan_button.text() == "Choose folder"
    assert not window._progress_bar.isVisible()
    files_page = window._pages["My Files"]
    dashboard = window._pages["Dashboard"]
    assert isinstance(files_page, MyFilesPage)
    assert isinstance(dashboard, DashboardPage)
    assert window._stack.currentWidget() is dashboard
    assert dashboard.scan_status.text() == "✓ Completed"
    assert dashboard.metadata_count.text() == "2 / 2"
    assert files_page._model.rowCount() == 2
    assert files_page._model.index(0, 0).data() == "meeting-notes.txt"
    assert files_page._model.index(0, 4).data() == "Documents"
    assert files_page._model.index(1, 4).data() == "Code"
    assert "2 files" in dashboard.inventory_details.text()
    assert "2 folders visited" in dashboard.inventory_details.text()
    assert {dashboard.categories.topLevelItem(i).text(0)
            for i in range(2)} == {"Documents", "Code"}
    dashboard.browse_button.click()
    assert window._stack.currentWidget() is files_page

    files_page._search.setText("not found")
    QTest.qWait(160)
    assert files_page._model.rowCount() == 0
    files_page._search.setText("meeting")
    QTest.qWait(160)
    assert files_page._model.rowCount() == 1
    files_page._search.clear()
    files_page._category_filter.setCurrentText("Code")
    assert files_page._model.rowCount() == 1
    assert files_page._model.index(0, 4).data() == "Code"
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
    assert "2 files hashed" in duplicate_page._summary.text()
    window.close()


def test_scan_can_be_cancelled_from_the_header(
    application: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from filemind.scanner.scanner import scan_directory

    started = Event()
    inventory_root = tmp_path / "completed"
    inventory_root.mkdir()
    (inventory_root / "previous.txt").write_text("previous scan", encoding="utf-8")
    cancelled_root = tmp_path / "cancelled"
    cancelled_root.mkdir()

    def wait_for_cancellation(
        directory: Path,
        progress_callback: Callable[[ScanProgress], None],
        cancellation_event: Event,
    ) -> ScanResult:
        if directory == inventory_root:
            return scan_directory(directory, progress_callback=progress_callback,
                                  cancellation_event=cancellation_event)
        started.set()
        progress_callback(ScanProgress(1, 0))
        cancellation_event.wait(2)
        return ScanResult(directory, (), (), 1, cancellation_event.is_set())

    monkeypatch.setattr("filemind.gui.workers.scan_directory", wait_for_cancellation)
    window = MainWindow(tmp_path / "history.db")
    files_page = window._pages["My Files"]
    window._start_scan(inventory_root)
    _wait_for_worker(application, window._scan_worker)
    window._start_scan(cancelled_root)
    worker = window._scan_worker
    assert worker is not None
    assert started.wait(1)

    window._handle_scan_button()
    _wait_for_worker(application, worker)

    assert window._scan_worker is None
    assert window._status_badge.text() == "SCAN CANCELLED"
    assert window._scan_button.isEnabled()
    assert not window._progress_bar.isVisible()
    assert files_page._model.rowCount() == 1
    assert files_page._model.index(0, 0).data() == "previous.txt"
    dashboard = window._pages["Dashboard"]
    assert str(cancelled_root) in dashboard.run_details.text()
    assert str(inventory_root) in dashboard.inventory_details.text()
    assert str(inventory_root) in window._header_subtitle.text()


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
        page._table.setCurrentIndex(page._model.index(1, 0))
        drain()
        page._table.setCurrentIndex(page._model.index(0, 0))
        drain()
        text = page._preview.toPlainText()
        assert "old content" not in text
        assert {"size": "updated longer content", "mtime": "new content", "replacement": "new content",
                "missing": "Could not read", "unreadable": "Could not read"}[change] in text
    finally:
        window.close()


def test_organizer_replaces_plan_after_completed_scan(application, tmp_path, monkeypatch):
    from test_moves import user_file
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    user_file(first / "report.txt", "report")
    window = MainWindow()
    try:
        page = window._pages["AI Organizer"]
        window._start_scan(first)
        _wait_for_worker(application, window._scan_worker)
        wait_plan(application, page)
        assert page.model.rowCount() == 1
        row = lambda col: page.model.index(0, col).data()
        assert row(0) == "report.txt"
        assert row(1) == str(Path("Organized") / "Documents" / "report.txt")
        assert row(3) == "READY"
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
    from datetime import datetime

    dashboard.set_scan_result(tmp_path, files, 1, datetime.now(), 0)
    documents = dashboard.categories.topLevelItem(0)
    assert documents.text(0) == "Documents"
    assert documents.text(1) == "2"
    assert documents.text(2) == "3 B (1/2)"
    assert documents.text(3) == ".txt (2)"
    graphs = dashboard.graphs
    assert graphs.canvas.mode == "Donut"
    assert graphs.canvas.total_label == "7 B"
    assert graphs.legend.topLevelItem(0).text(0) == "Code"
    assert graphs.insight.text() == "Code uses 57% of\nscanned storage"
    controls = {button.text(): button for button in graphs.findChildren(QPushButton)}
    controls["File count"].click()
    assert graphs.canvas.total_label == "3"
    assert graphs.legend.topLevelItem(0).text(0) == "Documents"
    assert graphs.insight.text() == "67% of scanned files\nare in Documents"
    for mode in ("Bar", "Treemap"):
        controls[mode].click()
        assert graphs.canvas.mode == mode
    dashboard.set_scan_result(tmp_path, [], 1, datetime.now(), 0)
    assert dashboard.categories.topLevelItem(0).text(1) == "0"
    assert "0 files" in dashboard.inventory_details.text()
    assert graphs.canvas.entries == []
    assert "No files" in graphs.empty.text()


def test_overview_chart_and_tree_use_completed_inventory(application, tmp_path):
    from datetime import datetime
    from filemind.categorizer.classifier import KNOWN_CATEGORIES

    folder = tmp_path / "Downloads"
    nested = folder / "test files"
    nested.mkdir(parents=True)
    files = []
    for path in (nested / "test1.txt", folder / "other.txt", folder / "model.glb"):
        path.touch()
        metadata = analyze_file(path, extract_content=False)
        files.append(ClassifiedFile(metadata, RuleBasedClassifier().classify(metadata)))

    dashboard = DashboardPage()
    dashboard.set_scan_result(folder, files, 2, datetime.now(), 0)
    chart = dashboard.categories
    rows = {chart.topLevelItem(index).text(0): chart.topLevelItem(index)
            for index in range(chart.topLevelItemCount())}
    assert rows.keys() == KNOWN_CATEGORIES
    assert rows["Documents"].text(1) == "2"
    assert rows["Documents"].text(4) == "█" * 12
    assert rows["3D Models"].text(4) == "█" * 6 + "░" * 6
    assert "66.7%" in rows["Documents"].toolTip(4)
    assert rows["Fonts"].text(1) == "0"
    assert rows["Fonts"].text(4) == "░" * 12

    tree = dashboard.file_tree.model()
    root = tree.index(0, 0)
    assert root.data() == "Downloads/"
    assert dashboard.file_tree.isExpanded(root)
    branch = tree.index(0, 0, root)
    assert branch.data() == "test files/"
    leaf = tree.index(0, 0, branch)
    assert leaf.data() == "test1.txt"
    assert leaf.data(Qt.ItemDataRole.ToolTipRole) == str(nested / "test1.txt")
    assert tree.parent(leaf) == branch
    assert tree.rowCount(leaf) == 0
    assert tree.rowCount(root) == 3

    dashboard.set_scan_result(tmp_path, [], 1, datetime.now(), 0)
    assert tree.rowCount(tree.index(0, 0)) == 0


def test_scan_warning_report_and_failed_rescan_keep_inventory(application, tmp_path, monkeypatch):
    from filemind.scanner.scanner import ScanIssue, scan_directory

    root = tmp_path / "inventory"
    root.mkdir()
    missing_file = root / "missing.txt"
    unreadable_folder = root / "private"
    issue = ScanIssue(unreadable_folder, "Permission denied")

    def scan_with_warnings(directory, **kwargs):
        if directory == root:
            return ScanResult(root, (missing_file,), (issue,), 2, False)
        return scan_directory(directory, **kwargs)

    monkeypatch.setattr("filemind.gui.workers.scan_directory", scan_with_warnings)
    window = MainWindow(tmp_path / "history.db")
    try:
        dashboard = window._pages["Dashboard"]
        window._start_scan(root)
        _wait_for_worker(application, window._scan_worker)
        assert window._stack.currentWidget() is dashboard
        assert dashboard.warnings.topLevelItem(0).text(1) == str(unreadable_folder)
        assert dashboard.warnings.topLevelItem(1).text(0) == "Metadata"
        assert "0/1 sizes" in dashboard.inventory_details.text()

        failed = tmp_path / "unavailable"
        window._start_scan(failed)
        _wait_for_worker(application, window._scan_worker)
        assert dashboard.scan_status.text() == "Failed"
        assert dashboard.run_error.text()
        assert str(failed) in dashboard.run_details.text()
        assert str(root) in dashboard.inventory_details.text()
        assert window._inventory_root == root
        assert window._pages["My Files"]._model.rowCount() == 1

        window._rescan_button.click()
        _wait_for_worker(application, window._scan_worker)
        assert window._latest_scan.root == root
    finally:
        window.close()


def test_organizer_selection_and_custom_folder(application, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    from test_moves import user_file
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = tmp_path / "report.txt"
    user_file(path, "report")
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

    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, title, message: pytest.fail(f"{title}: {message}"))

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

    def confirm(dialog):
        prompts.append(dialog.text())
        role = QMessageBox.AcceptRole if next(responses) == QMessageBox.Yes else QMessageBox.RejectRole
        QTimer.singleShot(0, next(button for button in dialog.buttons() if dialog.buttonRole(button) == role).click)
        return real_exec(dialog)
    real_exec = QMessageBox.exec
    monkeypatch.setattr(QMessageBox, "exec", confirm)
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
    assert history.selected_ids() == [history.model.rows[0]["id"]]
    assert history.button.isEnabled()
    history.button.click()
    _wait_for_worker(application, reopened._journal_worker)
    assert history.model.rows[0]["status"] == "undone"
    assert (folder / "a.txt").read_text() == "a.txt"
    assert not (folder / "Organized").exists()
    assert all("1 selected file" in prompt for prompt in prompts)
    assert len(prompts) == 3
    assert reopened.close()


def test_category_navigation_and_per_folder_preferences(application, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from PySide6.QtCore import QSettings
    from test_moves import user_file

    settings = QSettings(str(tmp_path / "profiles.ini"), QSettings.IniFormat)
    monkeypatch.setattr("filemind.gui.pages.QSettings", lambda *_: settings)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    folder = tmp_path / "Documents"
    folder.mkdir()
    user_file(folder / "paper.txt", "document")
    user_file(folder / "app.py", "code")
    window = MainWindow(tmp_path / "history.db")
    window._start_scan(folder)
    _wait_for_worker(application, window._scan_worker)
    page = window._pages["AI Organizer"]
    wait_plan(application, page)
    dashboard = window._pages["Dashboard"]
    node = next(dashboard.categories.topLevelItem(i)
                for i in range(dashboard.categories.topLevelItemCount())
                if dashboard.categories.topLevelItem(i).text(0) == "Documents")
    dashboard.categories.itemActivated.emit(node, 0)
    files = window._pages["My Files"]
    assert window._stack.currentWidget() is files and files._model.rowCount() == 1
    dashboard.review_button.click()
    assert window._stack.currentWidget() is page
    page.select_button.click()
    assert not page.selected_proposals()
    page.select_button.click()
    assert len(page.selected_proposals()) == 2
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: (".py", True))
    page.exclude_button.click()
    wait_plan(application, page)
    assert "1 excluded" in page._summary.text()
    window.close()
    reopened = MainWindow(tmp_path / "history.db")
    reopened._start_scan(folder)
    _wait_for_worker(application, reopened._scan_worker)
    page = reopened._pages["AI Organizer"]
    wait_plan(application, page)
    assert [r.current_path.name for r in page.selected_proposals()] == ["paper.txt"]
    page.set_scan_result(tmp_path, [])
    wait_plan(application, page)
    assert not page._excluded_types
    reopened.close()
