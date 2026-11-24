"""Main application window and persistent navigation."""

import logging
from datetime import datetime
from time import monotonic
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QSize, QSettings, QStandardPaths
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from filemind.analyzer.metadata import FileMetadata
from filemind.gui.theme import fixed_font
from filemind.gui.components import FeedbackButton, StatusBadge
from filemind.gui.icons import navigation_icon
from filemind.gui.motion import ScanProgress, SnapshotTransition, can_animate
from filemind.categorizer.classifier import ClassifiedFile
from filemind.duplicate_detector.detector import DuplicateProgress, DuplicateResult
from filemind.database.inventory import inventory
from filemind.gui.inventory_tools import ComparisonDialog, SearchDialog
from filemind.gui.cleanup import CleanupDialog
from filemind.gui.history import JournalWorker
from filemind.organizer.organizer import MoveJournal
from filemind.gui.pages import (
    DashboardPage,
    DuplicateFinderPage,
    MyFilesPage,
    PAGE_FACTORIES,
)
from filemind.gui.scan_report import ScanAttempt
from filemind.scanner.scanner import ScanIssue
from filemind.gui.workers import DirectoryScanWorker, DuplicateScanWorker


LOGGER = logging.getLogger(__name__)


PAGE_LABELS = {
    "Dashboard": "Overview",
    "AI Organizer": "Organizer",
    "Duplicate Finder": "Duplicates",
    "Activity History": "History && undo",
    "Settings": "About",
}

NAV_ITEMS = (
    ("Dashboard", "⌂"),
    ("My Files", "▤"),
    ("AI Organizer", "✦"),
    ("Duplicate Finder", "⧉"),
    ("Activity History", "◷"),
    ("Settings", "⚙"),
)


class WorkspacePages(QStackedWidget):
    """Let the scroll area size itself to the visible stage."""
    def minimumSizeHint(self):
        page = self.currentWidget()
        return page.minimumSizeHint() if page is not None else QSize(0, 0)


class MainWindow(QMainWindow):
    def __init__(self, history_path=None) -> None:
        super().__init__()
        self.setWindowTitle("FileMind")
        self.setMinimumSize(760, 530)
        self.resize(1280, 820)

        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}
        self._stack = WorkspacePages()
        self._stack.setObjectName("WorkspacePages")
        self._stack.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self._page_transition = SnapshotTransition(self._stack)
        self._scan_worker: DirectoryScanWorker | None = None
        self._duplicate_worker: DuplicateScanWorker | None = None
        self._scan_files: list[FileMetadata] = []
        self._has_scan = False
        self._inventory_root: Path | None = None
        self._latest_scan: ScanAttempt | None = None
        self._scan_started = 0.0
        self._appearance = QSettings("FileMind", "Appearance")
        self.reduce_motion = self._appearance.value("reduceMotion", False, type=bool)
        if history_path is None:
            location = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
            history_path = Path(location) / "moves.sqlite3"
        self._journal = MoveJournal(history_path)
        self._journal_worker = None
        root_layout.addWidget(self._build_header())
        body = QHBoxLayout()
        body.setSpacing(0)
        self.rail = self._build_sidebar()
        body.addWidget(self.rail)
        body.addWidget(self._build_content(), 1)
        root_layout.addLayout(body, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("LOCAL WORKSPACE   /   Ready")
        self._show_page("Dashboard")
        if self._journal.database.exists():
            self._run_journal("reconcile")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = event.size().width() < 940
        self.rail.setFixedWidth(56 if narrow else 185)
        for name, button in self._buttons.items():
            label = PAGE_LABELS.get(name, name)
            button.setText("" if narrow else label)
            button.setToolTip(label.replace("&&", "&"))
            button.setAccessibleName(label.replace("&&", "&"))
        orientation = Qt.Vertical if narrow else Qt.Horizontal
        self._pages["My Files"]._splitter.setOrientation(orientation)
        self._pages["AI Organizer"]._splitter.setOrientation(orientation)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(185)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 24, 8, 12)
        layout.setSpacing(4)
        for title, _ in NAV_ITEMS:
            if title == "Settings":
                layout.addStretch()
            button = FeedbackButton(PAGE_LABELS.get(title, title))
            button.setIcon(navigation_icon(title))
            button.setIconSize(QSize(17, 17))
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, name=title: self._show_page(name))
            self._buttons[title] = button
            layout.addWidget(button)
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("ContentArea")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)


        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        page_container = QWidget()
        page_container.setObjectName("PageContainer")
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(22, 21, 17, 16)
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
            dashboard.browse_requested.connect(lambda: self._show_page("My Files"))
            dashboard.review_requested.connect(lambda: self._show_page("AI Organizer"))
        duplicate_page = self._pages["Duplicate Finder"]
        if isinstance(duplicate_page, DuplicateFinderPage):
            duplicate_page.find_requested.connect(self._handle_duplicate_button)

        tool_button = self._pages["My Files"].tools_button
        menu = QMenu(tool_button)
        menu.addAction("Snapshots and folder comparison…", self._compare_inventory)
        menu.addAction("Search file contents…", self._content_search)
        menu.addAction("Cleanup…", self._cleanup)
        menu.addAction("Verified copy of selected file…", lambda: self._transfer("copy"))
        menu.addAction("Verified move of selected file…", lambda: self._transfer("move"))
        tool_button.setMenu(menu)
        motion = self._pages["Settings"].reduce_motion
        motion.setChecked(self.reduce_motion)
        motion.toggled.connect(self._set_reduce_motion)
        self._pages["AI Organizer"].apply_requested.connect(self._apply_moves)
        self._pages["Activity History"].undo_requested.connect(self._undo_moves)
        page_layout.addWidget(self._stack)
        scroll_area.setWidget(page_container)
        layout.addWidget(scroll_area, 1)
        return content

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        header.setMinimumHeight(61)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 8, 18, 8)

        icon = self.windowIcon()
        if not icon.isNull():
            brand_icon = QLabel()
            brand_icon.setPixmap(icon.pixmap(QSize(28, 28), self.devicePixelRatioF()))
            layout.addWidget(brand_icon)
        brand = QLabel("FileMind")
        brand.setObjectName("BrandName")
        layout.addWidget(brand)
        layout.addSpacing(20)
        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(2)
        self._header_title = QLabel()
        self._header_title.setObjectName("HeaderTitle")
        self._header_subtitle = QLabel()
        self._header_subtitle.setObjectName("HeaderSubtitle")
        self._header_subtitle.setFont(fixed_font())
        self._header_subtitle.setMinimumWidth(0)
        self._header_subtitle.setTextFormat(Qt.PlainText)
        self._header_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        heading_layout.addWidget(self._header_title)
        heading_layout.addWidget(self._header_subtitle)
        layout.addLayout(heading_layout, 1)

        self._status_badge = StatusBadge("LOCAL ONLY")
        self._rescan_button = FeedbackButton("Rescan")
        self._rescan_button.setEnabled(False)
        self._rescan_button.clicked.connect(self._rescan)
        self._progress_bar = ScanProgress()
        self._scan_button = FeedbackButton("Choose folder")
        self._scan_button.setObjectName("PrimaryButton")
        self._scan_button.clicked.connect(self._handle_scan_button)
        self._scan_button.setShortcut("Ctrl+O")
        self._scan_button.setToolTip("Choose a folder or cancel the current scan (Ctrl+O)")
        layout.addWidget(self._status_badge, 0, Qt.AlignVCenter)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._rescan_button)
        layout.addWidget(self._scan_button)
        self.statusBar().addPermanentWidget(QLabel("Ctrl+O"))
        return header

    def _show_page(self, page_name: str) -> None:
        page = self._pages[page_name]
        previous = self._stack.currentIndex()
        current = self._stack.indexOf(page)
        snapshot = None
        if current != previous and can_animate(self._stack):
            self._page_transition.clear()
            area = self._stack.visibleRegion().boundingRect()
            if not area.isEmpty():
                snapshot = self._stack.grab(area)
        self._stack.setCurrentWidget(page)
        self._stack.updateGeometry()
        self._header_title.setText(PAGE_LABELS.get(page_name, page_name).replace("&&", "&"))
        self._show_root()
        for name, button in self._buttons.items():
            button.setChecked(name == page_name)
        if snapshot is not None:
            start = QRectF(area)
            end = start.translated(-20 if current > previous else 20, 0)
            self._page_transition.play(snapshot, start, end, soften=True)

    def _show_root(self):
        root = self._inventory_root
        if root:
            text = f"INVENTORY  {root}"
        elif self._latest_scan:
            text = f"SCAN ROOT  {self._latest_scan.root}"
        else:
            text = "No folder scanned"
        self._header_subtitle.setText(text)
        self._header_subtitle.setToolTip(text)
        self._header_subtitle.setAccessibleName(text)

    def _set_reduce_motion(self, enabled):
        self.reduce_motion = enabled
        self._appearance.setValue("reduceMotion", enabled)
        for progress in self.findChildren(ScanProgress):
            progress.refresh_motion()
        self._pages["Dashboard"].scan_artwork.refresh_motion()
        if enabled:
            for transition in self.findChildren(SnapshotTransition):
                transition.clear()
            self._status_badge.update()

    def _confirm_moves(self, verb, count, details):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(f"{verb} selected moves")
        dialog.setText(f"{verb} {count:,} selected file operation(s)?")
        dialog.setDetailedText(details)
        dialog.setInformativeText("Undo a move restores the original. Undo a copy removes the destination after verifying the original."
                                  if verb == "Undo" else
                                  "Move the selected files to their proposed destinations. You can undo completed moves in History & undo.")
        cancel = dialog.addButton(QMessageBox.Cancel)
        accept = dialog.addButton(verb, QMessageBox.AcceptRole)
        accept.setObjectName("ReviewButton")
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        return dialog.clickedButton() == accept

    def _apply_moves(self):
        page = self._pages["AI Organizer"]
        selected = page.selected_proposals()
        root = page._directory
        metadata = {item.metadata.path: item.metadata for item in page._files}
        details = "\n".join(f"{p.current_path} → {p.destination}" for p in selected)
        if selected and self._confirm_moves("Apply", len(selected), details):
            self._run_journal("apply", root, selected, metadata)

    def _undo_moves(self, ids):
        selected = set(ids)
        rows = self._pages["Activity History"].model.rows
        details = "\n".join(f"{r['status']}: {r['original']} → {r['destination']}" for r in rows if r["id"] in selected)
        if ids and self._confirm_moves("Undo", len(ids), details):
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
        if worker.action != "reconcile":
            self._show_page("Activity History")
        if worker.error:
            QMessageBox.warning(self, "Activity History", worker.error)
        else:
            history.show_rows(worker.rows, worker.batch,
                              worker.args[0] if worker.action == "undo" else ())
        if worker.action != "reconcile":
            directory = self._pages["AI Organizer"]._directory
            if directory is not None:
                self._start_scan(directory)
        worker.deleteLater()

    def _inventory_view(self):
        return inventory(self._inventory_root, self._scan_files, self._inventory_issues)

    def _compare_inventory(self):
        dialog = ComparisonDialog(self, self._inventory_view(), self._journal.database.with_name("inventory.sqlite3"))
        dialog.exec()
        dialog.deleteLater()

    def _transfer(self, kind):
        page = self._pages["My Files"]
        index = page._table.currentIndex()
        if not index.isValid():
            self.statusBar().showMessage("Select a file in My Files first")
            return
        record = page._model.files[index.row()].metadata
        folder = QFileDialog.getExistingDirectory(self, f"Destination for verified {kind}")
        if not folder:
            return
        dest = Path(folder) / record.name
        if QMessageBox.question(self, f"Confirm verified {kind}",
                f"{kind.capitalize()} {record.path}\n\nto {dest}?", QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) == QMessageBox.Yes:
            self._run_journal("transfer", record.path, dest, record, kind)

    def _cleanup(self):
        downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
        dialog = CleanupDialog(self, self._inventory_root, self._scan_files, Path(downloads) if downloads else None,
                               self._journal)
        dialog.exec()
        if dialog.changed:
            self._rescan()
        dialog.deleteLater()

    def _content_search(self):
        dialog = SearchDialog(self, self._inventory_view(), self._journal.database.with_name("inventory.sqlite3"))
        if dialog.exec() and dialog.path:
            page = self._pages["My Files"]
            page._search.clear()
            page._category_filter.setCurrentIndex(0)
            page._filter_rows()
            for row, item in enumerate(page._model.files):
                if item.metadata.path == dialog.path:
                    page.inspector_toggle.setChecked(True)
                    page._table.setCurrentIndex(page._model.index(row, 0))
                    break
        dialog.deleteLater()

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
                self._latest_scan.status = "Cancelling"
                self._pages["Dashboard"].show_attempt(self._latest_scan)
                self._set_status("CANCELLING", muted=False)
            return
        self._choose_directory()

    def _rescan(self):
        root = self._inventory_root or (self._latest_scan.root if self._latest_scan else None)
        if root is not None:
            self._start_scan(root)

    def _start_scan(self, directory: Path) -> None:
        if self._duplicate_worker or self._scan_worker or self._journal_worker:
            return
        self._latest_scan = ScanAttempt(directory, datetime.now())
        self._scan_started = monotonic()
        self._show_root()
        self._rescan_button.setEnabled(False)
        worker = DirectoryScanWorker(directory)
        worker.progress.connect(self._on_scan_progress)
        worker.completed.connect(self._on_scan_completed)
        worker.failed.connect(self._on_scan_failed)
        worker.cancelled.connect(self._on_scan_cancelled)
        worker.finished.connect(self._on_scan_worker_finished)
        self._scan_worker = worker
        self._pages["My Files"].tools_button.setEnabled(False)
        self._pages["Duplicate Finder"]._find_button.setEnabled(False)
        self._pages["AI Organizer"].setEnabled(False)
        self._pages["Activity History"].setEnabled(False)
        self._scan_button.setText("Cancel scan")
        self._scan_button.setEnabled(True)
        self._progress_bar.begin()
        self._set_status("SCANNING", muted=False)

        dashboard = self._pages["Dashboard"]
        if isinstance(dashboard, DashboardPage):
            dashboard.show_attempt(self._latest_scan)
        worker.start()

    def _on_scan_progress(self, stage: str, current: int, total: int, folders: int) -> None:
        attempt = self._latest_scan
        attempt.folders = folders
        cancelling = attempt.status == "Cancelling"
        if stage == "Analyzing":
            attempt.discovered = total
            attempt.processed = current
            if total:
                self._progress_bar.report(current, total)
            progress = f"Metadata  ·  {current:,} of {total:,} files processed"
        else:
            attempt.discovered = current
            progress = f"Discovery  ·  {current:,} files found  ·  {folders:,} folders visited"
        if not cancelling:
            analyzing = stage == "Analyzing"
            attempt.status = "Reading metadata" if analyzing else "Discovering files"
            self._set_status("ANALYZING" if analyzing else "SCANNING", muted=False)
            self.statusBar().showMessage(progress)
        self._pages["Dashboard"].show_attempt(attempt)

    def _finish_scan_attempt(self, status, error=""):
        attempt = self._latest_scan
        attempt.status = status
        attempt.error = error
        attempt.finished = datetime.now()
        attempt.elapsed = monotonic() - self._scan_started
        result = self._scan_worker.result
        if result is not None:
            attempt.folders = result.directories_scanned
            attempt.discovered = len(result.files)
            attempt.discovery_issues = result.issues
        attempt.processed = self._scan_worker.metadata_processed
        attempt.metadata_issues = tuple(self._scan_worker.metadata_issues)
        self._pages["Dashboard"].show_attempt(attempt)
        return attempt

    def _on_scan_completed(
        self,
        directory: Path,
        files: list[ClassifiedFile],
        issues: tuple[ScanIssue, ...],
    ) -> None:
        warnings = len(issues) + len(self._scan_worker.metadata_issues)
        attempt = self._finish_scan_attempt("Completed with warnings" if warnings else "Completed")
        dashboard = self._pages["Dashboard"]
        dashboard.set_scan_result(directory, files, attempt.folders, attempt.finished, warnings)
        self._inventory_issues = issues
        self._inventory_root = directory
        self._scan_files = [item.metadata for item in files]
        self._has_scan = True
        self._pages["My Files"].set_scan_result(directory, files)
        self._pages["AI Organizer"].set_scan_result(directory, files)
        self._pages["Duplicate Finder"].set_scan_available(True)
        self._show_root()
        self._set_status("SCAN WARNINGS" if warnings else "LOCAL ONLY", muted=bool(warnings))
        if files and not warnings:
            self._status_badge.celebrate()
        self.statusBar().showMessage(
            f"Scan complete  ·  {len(files):,} files  ·  {attempt.folders:,} folders visited"
            f"  ·  {warnings:,} warnings"
        )

    def _on_scan_failed(self, directory: Path, message: str) -> None:
        self._finish_scan_attempt("Failed", message)
        self._set_status("SCAN FAILED", muted=True)
        self.statusBar().showMessage("Scan failed  ·  See Overview for the affected root and reason")

    def _on_scan_cancelled(self, directory: Path) -> None:
        self._finish_scan_attempt("Cancelled")
        self._set_status("SCAN CANCELLED", muted=True)
        if self._inventory_root:
            self.statusBar().showMessage("Scan cancelled  ·  Showing the previous completed inventory")

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
        if self._scan_worker or self._duplicate_worker or self._journal_worker:
            return
        if not self._has_scan:
            return

        worker = DuplicateScanWorker(self._scan_files)
        worker.progress.connect(self._on_duplicate_progress)
        worker.completed.connect(self._on_duplicate_completed)
        worker.failed.connect(self._on_duplicate_failed)
        worker.finished.connect(self._on_duplicate_worker_finished)
        self._duplicate_worker = worker
        self._pages["My Files"].tools_button.setEnabled(False)
        self._scan_button.setEnabled(False)
        self._rescan_button.setEnabled(False)
        self._pages["AI Organizer"].setEnabled(False)
        self._pages["Activity History"].setEnabled(False)
        self._progress_bar.begin(1000)
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
        self._progress_bar.report(min(value, 1000), 1000)
        self._set_status("HASHING", muted=True)

    def _on_duplicate_completed(self, result: DuplicateResult) -> None:
        duplicate_page = self._pages["Duplicate Finder"]
        if isinstance(duplicate_page, DuplicateFinderPage):
            if result.cancelled:
                duplicate_page.set_cancelled()
            else:
                duplicate_page.set_result(result)

        if result.cancelled:
            self._set_status("CHECK CANCELLED", muted=True)
            return

        if result.issues:
            for issue in result.issues:
                LOGGER.warning("Duplicate check skipped %s: %s", issue.path, issue.message)
            self._set_status("CHECK WARNINGS", muted=True)
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
        self._pages["My Files"].tools_button.setEnabled(self._has_scan)
        self._scan_button.setEnabled(True)
        self._rescan_button.setEnabled(self._latest_scan is not None)
        self._progress_bar.hide()
        if worker is not None:
            worker.deleteLater()

    def _on_scan_worker_finished(self) -> None:
        worker = self._scan_worker
        self._pages["AI Organizer"].setEnabled(True)
        self._pages["Activity History"].setEnabled(True)
        self._scan_worker = None
        self._pages["My Files"].tools_button.setEnabled(self._has_scan)
        self._pages["Duplicate Finder"]._find_button.setEnabled(self._has_scan)
        self._scan_button.setEnabled(True)
        self._scan_button.setText("Choose folder")
        self._rescan_button.setEnabled(self._latest_scan is not None)
        self._show_root()
        self._progress_bar.hide()
        if worker is not None:
            worker.deleteLater()

    def _set_status(self, text: str, muted: bool) -> None:
        self.statusBar().showMessage(f"{len(self._scan_files):,} files in workspace   ·   {text}")
        self._status_badge.set_status(text, muted)

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
