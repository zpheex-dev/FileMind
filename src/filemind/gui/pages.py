"""Page layouts for the FileMind desktop shell."""

from collections.abc import Callable
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableView,
    QSplitter,
    QTableWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filemind.gui.file_model import FileTableModel
from filemind.gui.workers import PreviewWorker

from filemind.gui.components import (
    EmptyState,
    MetricCard,
    SurfaceCard,
    add_card_heading,
    add_status_row,
)
from filemind.categorizer.classifier import ClassifiedFile
from filemind.duplicate_detector.detector import DuplicateProgress, DuplicateResult


class DashboardPage(QWidget):
    scan_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(18)

        layout.addWidget(self._build_welcome_card())
        layout.addLayout(self._build_metrics())
        layout.addLayout(self._build_overview_cards())
        layout.addStretch(1)

    def _build_welcome_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("WelcomeCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(18)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(7)
        title = QLabel("Your filesystem. In focus.")
        title.setObjectName("WelcomeTitle")
        description = QLabel(
            "Map your folders, inspect content, and find exact duplicates. All processing stays local. File moves require "
            "your review and confirmation."
        )
        description.setObjectName("MutedText")
        description.setWordWrap(True)
        text_layout.addWidget(title)
        text_layout.addWidget(description)

        self._scan_button = QPushButton("Scan a folder")
        self._scan_button.setObjectName("PrimaryButton")
        self._scan_button.clicked.connect(self.scan_requested.emit)

        layout.addLayout(text_layout, 1)
        layout.addWidget(self._scan_button, 0, Qt.AlignmentFlag.AlignVCenter)
        return card

    def _build_metrics(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(14)
        metrics = (
            ("Files found", "—", "Awaiting first scan"),
            ("Storage analyzed", "—", "Metadata not available yet"),
            ("Duplicate groups", "—", "Not checked yet"),
            ("Categories", "—", "Not classified yet"),
        )
        self._metric_cards: list[MetricCard] = []
        for label, value, note in metrics:
            card = MetricCard(label, value, note)
            self._metric_cards.append(card)
            layout.addWidget(card, 1)
        return layout

    def _build_overview_cards(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(14)

        scan_card = SurfaceCard()
        add_card_heading(
            scan_card.content_layout,
            "Scan overview",
            "Directory coverage and scan health.",
        )
        self._scan_empty_state = EmptyState(
            "No directory scanned",
            "Choose a folder to begin. Scanning includes accessible subfolders.",
            icon="⌕",
        )
        scan_card.content_layout.addWidget(self._scan_empty_state)

        activity_card = SurfaceCard()
        add_card_heading(
            activity_card.content_layout,
            "Category distribution",
            "Extension rules · local processing",
        )
        self._distribution_layout = QVBoxLayout()
        self._distribution_empty = QLabel("Scan a folder to reveal its file composition.")
        self._distribution_empty.setObjectName("MutedText")
        self._distribution_layout.addWidget(self._distribution_empty)
        activity_card.content_layout.addLayout(self._distribution_layout)
        activity_card.content_layout.addStretch(1)

        layout.addWidget(scan_card, 1)
        layout.addWidget(activity_card, 1)
        return layout

    def set_scan_running(self, directory: Path) -> None:
        self._scan_button.setEnabled(False)
        self._scan_empty_state.set_message(
            f"Scanning {directory.name}",
            "Discovering files and extracting supported metadata.",
        )

    def set_scan_failed(self, directory: Path) -> None:
        self._scan_button.setEnabled(True)
        self._scan_empty_state.set_message(
            "Scan failed",
            f"FileMind could not read {directory}. Your files were not changed.",
        )

    def set_scan_cancelled(self, directory: Path) -> None:
        self._scan_button.setEnabled(True)
        self._scan_empty_state.set_message(
            "Scan cancelled",
            f"The scan of {directory} was cancelled. Previous results were kept.",
        )

    def set_scan_result(
        self,
        directory: Path,
        files: list[ClassifiedFile],
        issue_count: int,
    ) -> None:
        self._scan_button.setEnabled(True)
        self._metric_cards[0].set_value(str(len(files)), f"in {directory.name}")
        sizes = [
            item.metadata.size_bytes
            for item in files
            if item.metadata.size_bytes is not None
        ]
        if len(sizes) == len(files):
            self._metric_cards[1].set_value(
                _format_size(sum(sizes)),
                "From the latest scan",
            )
        else:
            self._metric_cards[1].set_value(
                "—",
                f"Size available for {len(sizes)} of {len(files)} files",
            )
        category_counts = Counter(
            item.classification.category for item in files
        )
        while self._distribution_layout.count():
            entry = self._distribution_layout.takeAt(0)
            if entry.widget():
                entry.widget().deleteLater()
        for category, count in category_counts.most_common():
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 4, 0, 4)
            label = QLabel(category)
            label.setMinimumWidth(90)
            bar = QProgressBar()
            bar.setRange(0, len(files))
            bar.setValue(count)
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            count_label = QLabel(f"{count:,}  /  {count / len(files):.0%}")
            count_label.setMinimumWidth(72)
            row_layout.addWidget(label)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(count_label)
            self._distribution_layout.addWidget(row)
        self._metric_cards[3].set_value(
            str(len(category_counts)),
            "Rule-based categories",
        )
        message = f"Found {len(files)} files in {directory}, including subfolders."
        if issue_count:
            message += f" {issue_count} filesystem issue(s) need attention."
        self._scan_empty_state.set_message(
            "Scan complete",
            message,
        )


class MyFilesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(16)

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
        toolbar.addWidget(self._results_label)
        layout.addLayout(toolbar)

        self._model = FileTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)
        self._table = QTableView()
        self._table.setModel(self._proxy)
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
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        self._table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Interactive
        )
        for column, width in enumerate((210, 58, 75, 138, 105, 95, 220)):
            self._table.setColumnWidth(column, width)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setMinimumHeight(260)
        self._analyses: list[ClassifiedFile] = []

        self._view_stack = QStackedWidget()
        empty_card = SurfaceCard()
        self._empty_state = EmptyState(
            "No files to display",
            "Choose a folder to list files. This prototype does not modify them.",
            icon="▤",
        )
        empty_card.content_layout.addWidget(self._empty_state)
        self._view_stack.addWidget(empty_card)
        self._view_stack.addWidget(self._table)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._view_stack)

        self._preview_card = SurfaceCard()
        add_card_heading(
            self._preview_card.content_layout,
            "Content preview",
            "Extracted text stays on this device.",
        )
        self._preview = QPlainTextEdit()
        self._preview.setObjectName("ContentPreview")
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText("Select a file to preview its text.")
        self._preview.setMinimumHeight(150)
        self._preview_card.content_layout.addWidget(self._preview)
        self._preview_card.setVisible(False)
        self._splitter.addWidget(self._preview_card)
        self._splitter.setSizes([760, 340])
        layout.addWidget(self._splitter, 1)

        self._table.selectionModel().currentRowChanged.connect(
            lambda current, previous: self._display_selected_file(current.row(), 0, previous.row(), 0)
        )
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(120)
        self._search_timer.timeout.connect(self._filter_rows)
        self._search.textChanged.connect(lambda: self._search_timer.start())
        self._category_filter.currentTextChanged.connect(self._filter_rows)

    def set_scan_result(
        self,
        directory: Path,
        files: list[ClassifiedFile],
    ) -> None:
        self._analyses = files
        self._generation += 1
        self._preview_cache.clear()
        self._pending_preview = None
        self._model.set_files(files)
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
        self._preview_card.setVisible(bool(files))
        if files:
            self._view_stack.setCurrentWidget(self._table)
            self._table.setCurrentIndex(self._proxy.index(0, 0))
            self._display_selected_file(0, 0, -1, -1)
            self._filter_rows()
        else:
            self._empty_state.set_message(
                "No files found",
                f"No files were found in {directory} or its accessible subfolders.",
            )
            self._view_stack.setCurrentIndex(0)
            self._preview.clear()

    def _display_selected_file(
        self,
        row: int,
        _column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if not 0 <= row < self._proxy.rowCount():
            self._preview.clear()
            return

        source_row = self._proxy.mapToSource(self._proxy.index(row, 0)).row()
        classified_file = self._model.files[source_row]
        metadata = classified_file.metadata
        classification = classified_file.classification
        if metadata.content_status == "pending":
            cached = self._preview_cache.get(metadata.path)
            if cached is not None:
                metadata = cached
            else:
                self._preview.setPlainText(f"{metadata.name}\n\nLoading local preview...")
                self._pending_preview = metadata.path
                self._start_preview()
                return
        if metadata.content_status == "extracted":
            text = metadata.extracted_text or "No text content found."
            if metadata.content_truncated:
                text += "\n\n[Preview truncated for safety.]"
        elif metadata.content_status == "unsupported":
            text = (
                "No text extractor is available for "
                f"{metadata.extension or 'this file type'}."
            )
        else:
            text = (
                metadata.analysis_error or "Content could not be analyzed."
            )
        classification_details = (
            f"Rule-based category: {classification.category}\n"
            f"Rule score (not a probability): {classification.confidence:.0%}\n"
            f"Why: {classification.explanation}"
        )
        self._preview.setPlainText(f"{classification_details}\n\n{text}")

    def _start_preview(self):
        if self._closing or self._preview_worker is not None or self._pending_preview is None:
            return
        path = self._pending_preview
        self._pending_preview = None
        if path in self._preview_cache:
            return
        worker = PreviewWorker(path)
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
            source = self._proxy.mapToSource(current)
            selected = self._model.files[source.row()].metadata.path
            if metadata is None:
                self._preview.setPlainText("Preview could not be loaded.")
            elif selected == metadata.path:
                self._display_selected_file(current.row(), 0, -1, -1)

    def _preview_finished(self):
        worker = self._preview_worker
        self._preview_worker = None
        if worker is not None:
            worker.deleteLater()
        self._start_preview()

    def _filter_rows(self, _text: str = "") -> None:
        import re
        search = re.escape(self._search.text().strip())
        category = self._category_filter.currentText()
        # Apply category through a source model subset; the proxy handles text and sorting.
        files = self._analyses if category == "All categories" else [
            item for item in self._analyses if item.classification.category == category
        ]
        if self._model.files != files:
            self._model.set_files(files)
        self._proxy.setFilterRegularExpression(search)
        if self._proxy.rowCount():
            self._table.setCurrentIndex(self._proxy.index(0, 0))
        else:
            self._preview.clear()



def _format_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "—"
    if size_bytes < 1024:
        return f"{size_bytes} B"

    size = float(size_bytes)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
    return f"{size_bytes} B"


class OrganizerPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(18)
        layout.addLayout(self._build_steps())

        plan_card = SurfaceCard()
        row = QHBoxLayout()
        add_card_heading(
            plan_card.content_layout,
            "Organization plan",
            "Recommendations will include a destination and an explanation for each file.",
        )
        row.addStretch(1)
        add_status_row(row, "SCAN REQUIRED", muted=True)
        plan_card.content_layout.addLayout(row)
        plan_card.content_layout.addWidget(
            EmptyState(
                "No plan to review",
                "Scan a folder first. FileMind will present proposed moves for your approval and will not overwrite existing files.",
                icon="✦",
            )
        )
        layout.addWidget(plan_card)
        layout.addStretch(1)

    @staticmethod
    def _build_steps() -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)
        steps = (
            ("01", "Scan", "Read file information"),
            ("02", "Review", "Inspect proposed destinations"),
            ("03", "Confirm", "Approve selected moves"),
        )
        for number, title, description in steps:
            card = SurfaceCard()
            card.content_layout.setSpacing(6)
            number_label = QLabel(number)
            number_label.setObjectName("MutedText")
            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            detail_label = QLabel(description)
            detail_label.setObjectName("MutedText")
            detail_label.setWordWrap(True)
            card.content_layout.addWidget(number_label)
            card.content_layout.addWidget(title_label)
            card.content_layout.addWidget(detail_label)
            layout.addWidget(card, 1)
        return layout


class DuplicateFinderPage(QWidget):
    find_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(18)

        info_card = SurfaceCard()
        toolbar = QHBoxLayout()
        add_card_heading(
            info_card.content_layout,
            "Exact match detection",
            "SHA-256 hashes identify exact matches. Similar-looking files are not treated as duplicates.",
        )
        self._summary = QLabel("Scan a folder before checking for duplicates.")
        self._summary.setObjectName("MutedText")
        self._find_button = QPushButton("Find duplicates")
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
        self._tree.header().setStretchLastSection(True)
        self._view_stack.addWidget(self._tree)
        info_card.content_layout.addWidget(self._view_stack)
        layout.addWidget(info_card)
        layout.addStretch(1)

    def set_scan_available(self, available: bool) -> None:
        self._scan_available = available
        self._find_button.setEnabled(available)
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
            f"{_format_size(redundant_bytes)} potentially redundant"
        )
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


class ActivityHistoryPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(16)

        history_card = SurfaceCard()
        header = QHBoxLayout()
        add_card_heading(
            history_card.content_layout,
            "Operations",
            "Original and destination paths will be recorded for each successful move.",
        )
        header.addStretch(1)
        add_status_row(header, "UNDO AVAILABLE AFTER OPERATIONS", muted=True)
        history_card.content_layout.addLayout(header)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(
            ["Operation", "Original path", "New path", "Status"]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setMinimumHeight(200)
        history_card.content_layout.addWidget(table)
        history_card.content_layout.addWidget(
            EmptyState(
                "No operations recorded",
                "Completed file moves and their undo status will appear here.",
                icon="◷",
            )
        )
        layout.addWidget(history_card)
        layout.addStretch(1)


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(16)

        privacy_card = SurfaceCard()
        add_card_heading(
            privacy_card.content_layout,
            "Privacy",
            "FileMind is designed to keep file analysis on this device.",
        )
        privacy_card.content_layout.addWidget(
            EmptyState(
                "Local-first by design",
                "No file upload or cloud processing is configured. Privacy controls will be expanded as analysis features are implemented.",
                icon="⌂",
            )
        )

        preferences_card = SurfaceCard()
        add_card_heading(
            preferences_card.content_layout,
            "Scan preferences",
            "Scanning runs locally. Configurable exclusions and file types are planned.",
        )
        preferences_card.content_layout.addWidget(
            EmptyState(
                "No preferences to configure yet",
                "Excluded folders, supported file types, and classification options are planned.",
                icon="⚙",
            )
        )

        layout.addWidget(privacy_card)
        layout.addWidget(preferences_card)
        layout.addStretch(1)


PAGE_FACTORIES: dict[str, Callable[[], QWidget]] = {
    "Dashboard": DashboardPage,
    "My Files": MyFilesPage,
    "AI Organizer": OrganizerPage,
    "Duplicate Finder": DuplicateFinderPage,
    "Activity History": ActivityHistoryPage,
    "Settings": SettingsPage,
}
