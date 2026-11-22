"""Page layouts for the FileMind desktop shell."""

from collections.abc import Callable
import hashlib
import json
import os
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt, Signal, QTimer, QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QTableView,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filemind.gui.history import ActivityHistoryPage
from filemind.gui.proposals import PlanWorker, ProposalModel
from filemind.gui.file_model import FileTableModel, format_size as _format_size
from filemind.gui.motion import SnapshotTransition, can_animate
from filemind.gui.scan_report import DashboardPage
from filemind.gui.theme import fixed_font
from filemind.gui.workers import PreviewWorker

from filemind.gui.components import (
    EmptyState,
    FeedbackButton,
    SurfaceCard,
    add_card_heading,
    detail_label,
    reveal,
)
from filemind.categorizer.classifier import ClassifiedFile
from filemind.duplicate_detector.detector import DuplicateProgress, DuplicateResult


class MyFilesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by filename or location")
        self._search.setEnabled(False)
        self._category_filter = QComboBox()
        self._category_filter.addItem("All categories")
        self._category_filter.setEnabled(False)
        self._results_label = QLabel("No scan results yet")
        self._results_label.setObjectName("MutedText")
        toolbar.addWidget(self._search, 1)
        toolbar.addWidget(self._category_filter)
        self._results_label.setWordWrap(True)
        layout.addLayout(toolbar)
        layout.addWidget(self._results_label)

        self._model = FileTableModel(self)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().setMinimumSectionSize(24)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._preview_worker = None
        self._pending_preview = None
        self._preview_cache = {}
        self._generation = 0
        self._closing = False
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        for column, width in enumerate((185, 54, 72, 142, 108)):
            self._table.setColumnWidth(column, width)
        # The inspector shows the full location and the rule explanation.
        self._table.hideColumn(5)
        self._table.hideColumn(6)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setMinimumHeight(260)
        self._analyses: list[ClassifiedFile] = []
        self._selected_path: Path | None = None

        self._view_stack = QStackedWidget()
        empty_card = SurfaceCard()
        self._empty_state = EmptyState(
            "No files to display",
            "Choose a folder to browse its files.",
            icon="▤",
        )
        empty_card.content_layout.addWidget(self._empty_state)
        self._view_stack.addWidget(empty_card)
        self._view_stack.addWidget(self._table)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._view_stack)
        self._splitter.setChildrenCollapsible(False)

        self._preview_card = SurfaceCard()
        add_card_heading(
            self._preview_card.content_layout,
            "File inspector",
        )
        self._preview = QPlainTextEdit()
        self._preview.setObjectName("ContentPreview")
        self._preview.setFont(fixed_font())
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("Select a file to preview its text.")
        self._preview.setMinimumHeight(105)
        self._file_name = detail_label()
        self._file_name.setObjectName("CardTitle")
        self.file_details = detail_label()
        self.file_details.setFont(fixed_font())
        self._preview_status = QLabel("Select a file")
        self._preview_status.setObjectName("SectionCaption")
        self._copy = FeedbackButton("Copy path")
        self._copy.setEnabled(False)
        self._copy.clicked.connect(self._copy_path)
        self._open_folder = FeedbackButton("Open containing folder")
        self._open_folder.setEnabled(False)
        self._open_folder.clicked.connect(self._show_folder)
        actions = QHBoxLayout()
        actions.addWidget(self._copy)
        actions.addWidget(self._open_folder)
        actions.addStretch()
        self._preview_card.content_layout.addWidget(self._file_name)
        self._preview_card.content_layout.addLayout(actions)
        self._preview_card.content_layout.addWidget(self.file_details)
        self._preview_card.content_layout.addWidget(self._preview_status)
        self._preview_card.content_layout.addWidget(self._preview)
        self.inspector_toggle = FeedbackButton("Inspector")
        self.inspector_toggle.setCheckable(True)
        self.inspector_toggle.setChecked(True)
        self.inspector_toggle.toggled.connect(self._toggle_inspector)
        self.inspector_toggle.setEnabled(False)
        toolbar.addWidget(self.inspector_toggle)
        self._preview_card.setVisible(False)
        self._splitter.addWidget(self._preview_card)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes([680, 420])
        layout.addWidget(self._splitter, 1)
        self._file_transition = SnapshotTransition(self)

        self._table.selectionModel().currentRowChanged.connect(
            lambda current, previous: self._display_selected_file(current.row(), 0, previous.row(), 0)
        )
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(120)
        self._search_timer.timeout.connect(self._filter_rows)
        self._search.textChanged.connect(lambda: self._search_timer.start())
        self._category_filter.currentTextChanged.connect(self._filter_rows)

    def _toggle_inspector(self, visible):
        self._file_transition.clear()
        self._preview_card.setVisible(visible)
        if visible:
            reveal(self._preview_card, 160)

    def _copy_path(self):
        if self._selected_path is not None:
            QApplication.clipboard().setText(str(self._selected_path))

    def _show_folder(self):
        path = self._selected_path
        if path is not None and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent))):
            QMessageBox.warning(self, "Could not open folder", str(path.parent))

    def _clear_details(self):
        self._file_transition.clear()
        self._selected_path = None
        self._pending_preview = None
        self._copy.setEnabled(False)
        self._open_folder.setEnabled(False)
        self._preview.clear()
        self._file_name.clear()
        self.file_details.clear()
        self._preview_status.setText("Select a file")

    def set_scan_result(
        self,
        directory: Path,
        files: list[ClassifiedFile],
    ) -> None:
        self._analyses = files
        self._generation += 1
        self._preview_cache.clear()
        self._pending_preview = None
        categories = {item.classification.category for item in files}
        self._search.clear()
        self._search.setEnabled(bool(files))
        self._category_filter.blockSignals(True)
        self._category_filter.clear()
        self._category_filter.addItem("All categories")
        self._category_filter.addItems(sorted(categories, key=str.casefold))
        self._category_filter.setEnabled(bool(files))
        self._category_filter.blockSignals(False)
        self._results_label.setText(f"{len(files):,} files")
        self._results_label.setToolTip(str(directory))
        self.inspector_toggle.setEnabled(bool(files))
        self._preview_card.setVisible(bool(files) and self.inspector_toggle.isChecked())
        if files:
            self._view_stack.setCurrentWidget(self._table)
            self._filter_rows()
        else:
            self._model.set_files([])
            self._empty_state.set_message(
                "No files found",
                f"No files were found in {directory} or its accessible subfolders.",
            )
            self._view_stack.setCurrentIndex(0)
            self._clear_details()

    def _display_selected_file(
        self,
        row: int,
        _column: int,
        previous_row: int,
        _previous_column: int,
        preview_metadata=None,
    ) -> None:
        if not 0 <= row < self._model.rowCount():
            self._clear_details()
            return

        classified_file = self._model.files[row]
        scanned = classified_file.metadata
        metadata = preview_metadata if preview_metadata is not None else scanned
        classification = classified_file.classification
        changed_selection = (preview_metadata is None and previous_row >= 0
                             and self._selected_path != scanned.path)
        self._selected_path = scanned.path
        self._file_name.setText(scanned.name)
        self._copy.setEnabled(True)
        self._open_folder.setEnabled(True)
        size = ("Unavailable" if metadata.size_bytes is None else
                f"{metadata.size_bytes:,} bytes ({_format_size(metadata.size_bytes)})")
        modified = (f"{metadata.modified_at:%Y-%m-%d %H:%M:%S} local"
                    if metadata.modified_at else "Unavailable")
        created = (f"{metadata.created_at:%Y-%m-%d %H:%M:%S} local"
                   if metadata.created_at else "Unavailable")
        changed = preview_metadata is not None and (
            scanned.identity, scanned.size_bytes, scanned.modified_at_ns
        ) != (metadata.identity, metadata.size_bytes, metadata.modified_at_ns)
        details = [
            str(scanned.path),
            f"Type        {metadata.extension or 'No extension'}",
            f"Size        {size}",
            f"Modified    {modified}",
            f"Created     {created}",
            f"Category    {classification.category}",
            f"Rule        {classification.explanation}",
            f"Strength    {classification.confidence:.0%} (heuristic)",
        ]
        if changed:
            details.append("File differs from the scanned inventory")
        if scanned.analysis_error:
            details.append(f"Scan issue  {scanned.analysis_error}")
        self.file_details.setText("\n".join(details))
        if preview_metadata is None:
            if changed_selection:
                self._animate_file_name(row, scanned.name)
            self._preview_status.setText("PREVIEW  ·  LOADING")
            self._preview.clear()
            self._pending_preview = metadata.path
            self._start_preview()
            return

        if metadata.content_status == "extracted":
            status = "Truncated" if metadata.content_truncated else "Ready"
            text = metadata.extracted_text or "No text content found."
        elif metadata.content_status == "unsupported":
            status = "Unsupported"
            text = f"No text preview for {metadata.extension or 'files with no extension'}."
        else:
            status = "Skipped" if metadata.content_status == "skipped" else "Unreadable"
            text = metadata.analysis_error or "Content could not be analyzed."
        self._preview_status.setText(f"PREVIEW  ·  {status.upper()}")
        self._preview.setPlainText(text)
        reveal(self._preview.viewport(), 160, 0.7)

    def _animate_file_name(self, row, name):
        self._file_transition.clear()
        if not can_animate(self._file_name):
            return
        viewport = self._table.viewport()
        cell = self._table.visualRect(self._model.index(row, 0))
        metrics = self._table.fontMetrics()
        cell.setWidth(min(cell.width(), metrics.horizontalAdvance(name) + 10))
        cell.adjust(0, 4, 0, -4)
        cell = cell.intersected(viewport.rect())
        if cell.isEmpty():
            return
        start = QRectF(cell.translated(viewport.mapTo(self, QPoint())))
        title = self._file_name
        end = QRectF(title.rect())
        end.moveTopLeft(title.mapTo(self, QPoint()))
        end.setWidth(min(end.width(), title.fontMetrics().horizontalAdvance(name) + 12))
        self._file_transition.play(viewport.grab(cell), start, end)
        reveal(title, 240, 0.35)

    def _start_preview(self):
        if self._closing or self._preview_worker is not None or self._pending_preview is None:
            return
        path = self._pending_preview
        self._pending_preview = None
        worker = PreviewWorker(path, self._preview_cache.pop(path, None))
        worker.generation = self._generation
        self._preview_worker = worker
        worker.completed.connect(self._preview_completed)
        worker.finished.connect(self._preview_finished)
        worker.start()

    def _preview_completed(self, metadata):
        if self._preview_worker.generation != self._generation:
            return
        if metadata is not None:
            # A bounded cache avoids retaining text for the entire scan.
            if len(self._preview_cache) >= 8:
                self._preview_cache.pop(next(iter(self._preview_cache)))
            self._preview_cache[metadata.path] = metadata
        current = self._table.currentIndex()
        if current.isValid():
            selected = self._model.files[current.row()].metadata.path
            if metadata is None and selected == self._preview_worker.path:
                self._preview_status.setText("PREVIEW  ·  UNREADABLE")
                self._preview.setPlainText("Preview could not be loaded.")
            elif metadata is not None and selected == metadata.path:
                self._display_selected_file(current.row(), 0, -1, -1, metadata)

    def _preview_finished(self):
        worker = self._preview_worker
        self._preview_worker = None
        if worker is not None:
            worker.deleteLater()
        self._start_preview()

    def _filter_rows(self, _text: str = "") -> None:
        self._search_timer.stop()
        search = self._search.text().strip().casefold()
        category = self._category_filter.currentText()
        files = self._analyses if category == "All categories" else [
            item for item in self._analyses if item.classification.category == category
        ]
        self._model.set_files(files, search)
        count = self._model.rowCount()
        known_sizes = [item.metadata.size_bytes for item in self._model.files
                       if item.metadata.size_bytes is not None]
        coverage = f" ({len(known_sizes):,}/{count:,} sizes)" if len(known_sizes) != count else ""
        self._results_label.setText(
            f"{count:,} of {len(self._analyses):,} files  ·  "
            f"{_format_size(sum(known_sizes))} known{coverage}"
        )
        if count:
            self._table.setCurrentIndex(self._model.index(0, 0))
        else:
            self._clear_details()


class OrganizerPage(QWidget):
    apply_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        card = SurfaceCard()
        add_card_heading(
            card.content_layout,
            "Review moves",
            "Choose the files to move into Organized. Blocked files stay in place.",
        )
        self._summary = QLabel("Scan a folder to generate a plan.")
        self._summary.setWordWrap(True)
        card.content_layout.addWidget(self._summary)
        controls = QHBoxLayout()
        self._folder_button = FeedbackButton("Destinations…")
        self._folder_button.setEnabled(False)
        self._folder_button.clicked.connect(self._customize_folder)
        controls.addWidget(self._folder_button)
        self.exclude_button = FeedbackButton("Exclusions…")
        self.exclude_button.setEnabled(False)
        self.exclude_button.clicked.connect(self._edit_exclusions)
        controls.addWidget(self.exclude_button)
        self.select_button = FeedbackButton("Clear selection")
        self.select_button.setEnabled(False)
        self.select_button.clicked.connect(self._toggle_selection)
        controls.addWidget(self.select_button)
        self.apply_button = FeedbackButton("Review moves")
        self.apply_button.setObjectName("ReviewButton")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_requested)
        controls.addStretch(1)
        card.content_layout.addLayout(controls)
        self.model = ProposalModel(self)
        self.model.dataChanged.connect(self._update_apply)
        self.model.modelReset.connect(self._update_apply)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setDefaultSectionSize(185)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 225)
        self.table.setColumnWidth(3, 105)
        self.table.hideColumn(2)
        self.table.setMinimumHeight(220)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self.table)
        inspector = SurfaceCard()
        add_card_heading(inspector.content_layout, "Move details")
        self.route = detail_label("Select a proposal to inspect its full route.")
        inspector.content_layout.addWidget(self.route)
        inspector.content_layout.addStretch()
        self._splitter.addWidget(inspector)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes([660, 350])
        toggle = FeedbackButton("Inspector")
        toggle.setCheckable(True)
        toggle.setChecked(True)
        toggle.toggled.connect(inspector.setVisible)
        toggle.toggled.connect(lambda visible: reveal(inspector, 160) if visible else None)
        controls.insertWidget(controls.count() - 1, toggle)
        card.content_layout.addWidget(self._splitter, 1)
        footer = QHBoxLayout()
        footer.addWidget(QLabel("Changes require confirmation"))
        footer.addStretch()
        footer.addWidget(self.apply_button)
        card.content_layout.addLayout(footer)
        self.table.selectionModel().currentRowChanged.connect(self._inspect_route)
        self.model.modelReset.connect(self._inspect_route)
        layout.addWidget(card)
        self._excluded_count = 0
        self.generation = 0
        self.workers = set()
        self._folder_names = {}
        self._excluded_types = set()
        self._settings = QSettings("FileMind", "FolderProfiles")
        self._directory = None
        self._files = []

    def _inspect_route(self, index=None, previous=None):
        if index is not None and index.isValid():
            proposal = self.model.rows[index.row()]
            status = "; ".join(proposal.conflicts) if proposal.has_conflict else "Ready"
            self.route.setText(
                f"FROM\n{proposal.current_path}\n\nTO\n{proposal.destination}"
                f"\n\nREASON\n{proposal.reason}\n\nSTATUS\n{status}"
            )
        else:
            self.route.setText("Select a proposal to inspect its full route.")

    def _customize_folder(self):
        categories = sorted({item.classification.category for item in self._files})
        category, accepted = QInputDialog.getItem(
            self, "Category folder", "Choose a category:", categories, 0, False
        )
        if not accepted:
            return
        folder, accepted = QInputDialog.getText(
            self, "Category folder", "Folder name inside Organized:",
            text=self._folder_names.get(category, category),
        )
        if not accepted:
            return
        updated = dict(self._folder_names)
        updated[category] = folder
        try:
            from filemind.organizer.planner import validate_folder
            validate_folder(folder)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid folder name", str(error))
            return
        self._folder_names = updated
        self._save_profile()
        self._build_plan()

    def _profile_key(self):
        path = os.fsencode(os.path.normcase(str(self._directory)))
        return "folders/" + hashlib.sha256(path).hexdigest()

    def _save_profile(self):
        self._settings.setValue(self._profile_key(), json.dumps({
            "folders": self._folder_names, "excluded": sorted(self._excluded_types)
        }))

    def _edit_exclusions(self):
        text, ok = QInputDialog.getText(self, "Organizer exclusions",
            "Skip these file extensions in this folder (comma-separated):",
            text=", ".join(sorted(self._excluded_types)))
        if ok:
            self._excluded_types = {part.strip().lower().lstrip(".") for part in text.split(",") if part.strip().lstrip(".")}
            self._save_profile()
            self._build_plan()

    def _toggle_selection(self):
        if self.selected_proposals():
            self.model.unchecked.update(row.current_path for row in self.model.rows if not row.has_conflict)
        else:
            self.model.unchecked.difference_update(row.current_path for row in self.model.rows if not row.has_conflict)
        self.model.replace(self.model.rows)

    def _update_apply(self):
        selected = len(self.selected_proposals())
        self.apply_button.setEnabled(bool(selected))
        self.apply_button.setText(f"Review {selected:,} moves" if selected else "Review moves")
        self.select_button.setEnabled(any(not row.has_conflict for row in self.model.rows))
        self.select_button.setText("Clear selection" if selected else "Select eligible")
        blocked = sum(row.has_conflict for row in self.model.rows)
        self._summary.setText(
            f"{len(self.model.rows):,} proposed   ·   {selected:,} selected   ·   "
            f"{blocked:,} blocked   ·   {self._excluded_count:,} excluded"
        )

    def selected_proposals(self):
        return tuple(row for row in self.model.rows
                     if not row.has_conflict and row.current_path not in self.model.unchecked)

    def set_scan_result(self, directory, files):
        if directory != self._directory:
            self.model.unchecked.clear()
        self._directory, self._files = directory, files
        self.model.directory = directory
        try:
            profile = json.loads(self._settings.value(self._profile_key(), "{}"))
            self._folder_names = dict(profile.get("folders", {}))
            self._excluded_types = set(profile.get("excluded", []))
        except (ValueError, TypeError, AttributeError):
            self._folder_names, self._excluded_types = {}, set()
        self.exclude_button.setEnabled(bool(files))
        self._folder_button.setEnabled(bool(files))
        self._build_plan()

    def _build_plan(self):
        self.generation += 1
        included = [item for item in self._files
                    if item.metadata.extension.lstrip(".").lower() not in self._excluded_types]
        self._excluded_count = len(self._files) - len(included)
        self.model.replace(())
        self._summary.setText("Checking destinations…")
        worker = PlanWorker(self.generation, self._directory, included, dict(self._folder_names), self)
        self.workers.add(worker)
        worker.ready.connect(self._accept_plan)
        worker.finished.connect(self._worker_finished)
        worker.start()

    def _worker_finished(self):
        worker = self.sender()
        self.workers.discard(worker)
        worker.deleteLater()

    def _accept_plan(self, generation, rows, error):
        if generation == self.generation:
            self.model.replace(rows)
            if rows:
                self.table.setCurrentIndex(self.model.index(0, 0))
            if error:
                self._summary.setText(error)



class DuplicateFinderPage(QWidget):
    find_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        info_card = SurfaceCard()
        toolbar = QHBoxLayout()
        add_card_heading(
            info_card.content_layout,
            "Exact match detection",
            "Read-only SHA-256 check of files with matching sizes.",
        )
        self._summary = QLabel("Scan a folder before checking for duplicates.")
        self._summary.setObjectName("MutedText")
        self._summary.setWordWrap(True)
        self._find_button = FeedbackButton("Find duplicates")
        self._find_button.setObjectName("PrimaryButton")
        self._find_button.setEnabled(False)
        self._find_button.clicked.connect(self.find_requested.emit)
        self._scan_available = False
        toolbar.addWidget(self._summary, 1)
        toolbar.addWidget(self._find_button)
        info_card.content_layout.addLayout(toolbar)

        self._view_stack = QStackedWidget()
        self._empty_state = EmptyState(
            "Scan a folder first",
            "Duplicate detection is exact and read-only. FileMind will never remove duplicates.",
            icon="⧉",
        )
        self._view_stack.addWidget(self._empty_state)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(
            ["File or group", "Size", "Redundant", "SHA-256", "Location"]
        )
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setColumnWidth(0, 240)
        self._tree.setColumnWidth(1, 100)
        self._tree.setColumnWidth(2, 110)
        self._tree.setColumnWidth(3, 300)
        self._tree.header().moveSection(4, 3)
        self._tree.setColumnWidth(4, 340)
        self._tree.header().setStretchLastSection(True)
        self._view_stack.addWidget(self._tree)
        self._tree.setMinimumHeight(200)
        info_card.content_layout.addWidget(self._view_stack, 1)
        self._issues = QTreeWidget()
        self._issues.setHeaderLabels(("SKIPPED PATH", "REASON"))
        self._issues.setRootIsDecorated(False)
        self._issues.setColumnWidth(0, 370)
        self._issues.setMinimumHeight(105)
        self._issues.hide()
        info_card.content_layout.addWidget(self._issues)
        layout.addWidget(info_card, 1)

    def set_scan_available(self, available: bool) -> None:
        self._scan_available = available
        self._find_button.setEnabled(available)
        self._find_button.setText("Find duplicates")
        self._issues.clear()
        self._issues.hide()
        if not available:
            self._tree.clear()
            self._summary.setText("Scan a folder before checking for duplicates.")
            self._empty_state.set_message(
                "Scan a folder first",
                "Duplicate detection is exact and read-only. FileMind will never remove duplicates.",
            )
            self._view_stack.setCurrentWidget(self._empty_state)
        else:
            self._tree.clear()
            self._summary.setText("Ready to check the latest scan.")
            self._empty_state.set_message(
                "Ready to find duplicates",
                "Only same-size candidates are hashed. No files will be removed.",
            )
            self._view_stack.setCurrentWidget(self._empty_state)

    def set_running(self) -> None:
        self._find_button.setText("Cancel check")
        self._find_button.setEnabled(True)
        self._summary.setText("Hashing same-size candidates…")

    def set_cancelling(self) -> None:
        self._find_button.setText("Cancelling...")
        self._find_button.setEnabled(False)
        self._summary.setText("Stopping duplicate check...")

    def set_progress(self, progress: DuplicateProgress) -> None:
        if progress.total_files:
            self._summary.setText(
                f"Checking candidate {progress.files_processed} of "
                f"{progress.total_files} · {progress.bytes_hashed:,} bytes hashed"
            )

    def set_cancelled(self) -> None:
        self._find_button.setText("Check again")
        self._find_button.setEnabled(self._scan_available)
        self._summary.setText("Check cancelled; previous results were kept.")
        if self._tree.topLevelItemCount() == 0:
            self._empty_state.set_message(
                "Duplicate check cancelled",
                "Run the check again when you are ready.",
            )
            self._view_stack.setCurrentWidget(self._empty_state)

    def set_result(self, result: DuplicateResult) -> None:
        self._find_button.setText("Check again")
        self._find_button.setEnabled(self._scan_available)
        self._tree.clear()
        for group in result.groups:
            group_item = QTreeWidgetItem(
                [
                    f"{len(group.files)} identical files",
                    _format_size(group.size_bytes),
                    _format_size(group.redundant_bytes),
                    group.sha256,
                    "",
                ]
            )
            group_item.setToolTip(3, group.sha256)
            for path in group.files:
                file_item = QTreeWidgetItem(
                    [path.name, _format_size(group.size_bytes), "", "", str(path.parent)]
                )
                file_item.setToolTip(0, str(path))
                group_item.addChild(file_item)
            group_item.setExpanded(True)
            self._tree.addTopLevelItem(group_item)

        redundant_bytes = sum(group.redundant_bytes for group in result.groups)
        self._summary.setText(
            f"{len(result.groups)} groups · "
            f"{_format_size(redundant_bytes)} recoverable (estimate) · "
            f"{result.files_hashed:,} files hashed · {len(result.issues):,} skipped"
        )
        self._issues.clear()
        for issue in result.issues:
            row = QTreeWidgetItem((str(issue.path), issue.message))
            row.setToolTip(0, str(issue.path))
            row.setToolTip(1, issue.message)
            self._issues.addTopLevelItem(row)
        self._issues.setVisible(bool(result.issues))
        if result.groups:
            self._view_stack.setCurrentWidget(self._tree)
        else:
            title = (
                "No exact duplicates found"
                if not result.issues
                else "No duplicate groups could be confirmed"
            )
            description = (
                f"Hashed {result.files_hashed} same-size candidate file(s). "
                "No files were changed."
            )
            if result.issues:
                description += f" {len(result.issues)} file issue(s) occurred."
            self._empty_state.set_message(title, description)
            self._view_stack.setCurrentWidget(self._empty_state)


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = SurfaceCard()
        add_card_heading(card.content_layout, "FileMind", "Local desktop file organizer  ·  Version 0.3.0")
        note = QLabel("Scans and exact duplicate checks run on this device. Review moves in Organizer and restore them from History.")
        note.setWordWrap(True)
        card.content_layout.addWidget(note)
        self.reduce_motion = QCheckBox("Reduce motion")
        card.content_layout.addWidget(self.reduce_motion)
        layout.addWidget(card)
        layout.addStretch(1)


PAGE_FACTORIES: dict[str, Callable[[], QWidget]] = {
    "Dashboard": DashboardPage,
    "My Files": MyFilesPage,
    "AI Organizer": OrganizerPage,
    "Duplicate Finder": DuplicateFinderPage,
    "Activity History": ActivityHistoryPage,
    "Settings": SettingsPage,
}
