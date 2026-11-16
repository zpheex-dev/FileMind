"""Page layouts for the FileMind desktop shell."""

from collections.abc import Callable
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

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
        title = QLabel("Your files, understood.")
        title.setObjectName("WelcomeTitle")
        description = QLabel(
            "Start with a local scan. FileMind will never move files without "
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
            "Your latest scan summary will appear here.",
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
            "Recent activity",
            "A record of completed organization actions.",
        )
        activity_card.content_layout.addWidget(
            EmptyState(
                "Nothing here yet",
                "Completed operations and their undo status will be shown here.",
                icon="◷",
            )
        )

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
        self._metric_cards[3].set_value(
            str(len(category_counts)),
            "Rule-based categories",
        )
        message = f"Found {len(files)} files in {directory}, including subfolders."
        if category_counts:
            distribution = ", ".join(
                f"{category}: {count}"
                for category, count in sorted(
                    category_counts.items(),
                    key=lambda item: item[0].casefold(),
                )
            )
            message += f" Rule-based distribution: {distribution}."
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

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Name", "Type", "Size", "Modified", "Category", "Confidence", "Location"]
        )
        self._table.horizontalHeaderItem(5).setToolTip(
            "Heuristic rule strength, not a model probability."
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch
        )
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
        layout.addWidget(self._view_stack)

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
        layout.addWidget(self._preview_card)

        self._table.currentCellChanged.connect(self._display_selected_file)
        self._search.textChanged.connect(self._filter_rows)
        self._category_filter.currentTextChanged.connect(self._filter_rows)
        layout.addStretch(1)

    def set_scan_result(
        self,
        directory: Path,
        files: list[ClassifiedFile],
    ) -> None:
        self._analyses = files
        self._table.setRowCount(len(files))
        categories: set[str] = set()
        for row, classified_file in enumerate(files):
            metadata = classified_file.metadata
            classification = classified_file.classification
            categories.add(classification.category)
            file_type = metadata.extension[1:].upper() if metadata.extension else "—"
            modified = (
                metadata.modified_at.strftime("%Y-%m-%d %H:%M")
                if metadata.modified_at is not None
                else "—"
            )
            for column, value in enumerate(
                (
                    metadata.name,
                    file_type,
                    _format_size(metadata.size_bytes),
                    modified,
                    classification.category,
                    f"{classification.confidence:.0%}",
                    str(metadata.path.parent),
                )
            ):
                self._table.setItem(row, column, QTableWidgetItem(value))

        self._search.clear()
        self._search.setEnabled(bool(files))
        self._category_filter.blockSignals(True)
        self._category_filter.clear()
        self._category_filter.addItem("All categories")
        self._category_filter.addItems(sorted(categories, key=str.casefold))
        self._category_filter.setEnabled(bool(files))
        self._category_filter.blockSignals(False)
        self._results_label.setText(f"{len(files)} files · {directory}")
        self._preview_card.setVisible(bool(files))
        if files:
            self._view_stack.setCurrentWidget(self._table)
            self._table.setCurrentCell(0, 0)
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
        if not 0 <= row < len(self._analyses):
            self._preview.clear()
            return

        classified_file = self._analyses[row]
        metadata = classified_file.metadata
        classification = classified_file.classification
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

    def _filter_rows(self, _text: str = "") -> None:
        search_text = self._search.text().casefold().strip()
        selected_category = self._category_filter.currentText()
        for row in range(self._table.rowCount()):
            row_text = " ".join(
                self._table.item(row, column).text()
                for column in range(self._table.columnCount())
                if self._table.item(row, column) is not None
            )
            category = self._table.item(row, 4)
            category_matches = (
                selected_category == "All categories"
                or (
                    category is not None
                    and category.text() == selected_category
                )
            )
            self._table.setRowHidden(
                row,
                search_text not in row_text.casefold() or not category_matches,
            )


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
            "These controls will be available when scanning is implemented.",
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
