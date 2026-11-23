"""The most recent scan attempt and the inventory it has produced."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView, QBoxLayout, QHeaderView, QHBoxLayout, QLabel, QStyle,
    QStyledItemDelegate, QStyleOptionViewItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from filemind.categorizer.classifier import KNOWN_CATEGORIES
from filemind.gui.components import (
    FeedbackButton, StatusBadge, SurfaceCard, add_card_heading, detail_label, divider,
)
from filemind.gui.file_model import format_size
from filemind.gui.icons import metric_icon
from filemind.gui.inventory_graphs import InventoryGraphs
from filemind.gui.motion import ScanProgress, can_animate, tween
from filemind.gui.path_model import ScanPathModel, ScanPathTree
from filemind.gui.theme import ACTIVE, AMBER, TRACK, fixed_font
from filemind.scanner.scanner import ScanIssue


@dataclass
class ScanAttempt:
    root: Path
    started: datetime
    finished: datetime | None = None
    elapsed: float | None = None
    status: str = "Discovering files"
    folders: int = 0
    discovered: int = 0
    processed: int = 0
    discovery_issues: tuple[ScanIssue, ...] = ()
    metadata_issues: tuple[ScanIssue, ...] = ()
    error: str = ""


class ScanArtwork(QWidget):
    """Open the folder icon while the inventory is being scanned."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(30, 30)
        self._busy = False
        self._morph = tween(self, 420)
        self._morph.setEndValue(0.0)
        self._morph.valueChanged.connect(lambda _: self.update())

    def set_busy(self, busy):
        if busy == self._busy:
            return
        self._busy = busy
        phase = self._morph.currentValue()
        self._morph.stop()
        self._morph.setStartValue(phase)
        self._morph.setEndValue(float(busy))
        if can_animate(self):
            self._morph.start()
        else:
            self.refresh_motion()

    def refresh_motion(self):
        if not can_animate(self):
            self._morph.stop()
            self._morph.setCurrentTime(self._morph.duration())
        self.update()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._morph.stop()
        self._morph.setCurrentTime(self._morph.duration())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(0.67, 0.82)
        pen = QPen(QColor(ACTIVE), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        folder = [(-18, 12), (-18, -11), (-5, -11), (-1, -7), (18, -7), (18, 12), (-18, 12)]
        open_folder = [(-19, 13), (-13, -6), (-5, -6), (-1, -10), (21, -10), (15, 13), (-19, 13)]
        phase = self._morph.currentValue() if can_animate(self) else float(self._busy)
        painter.drawPolyline(QPolygonF([
            QPointF(x + (ex - x) * phase, y + (ey - y) * phase)
            for (x, y), (ex, ey) in zip(folder, open_folder)
        ]))


class CountBars(QStyledItemDelegate):
    def paint(self, painter, option, index):
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        item.text = ""
        item.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, item, painter, item.widget)
        bar = QRectF(item.rect).adjusted(7, 0, -12, 0)
        bar.setTop(bar.center().y() - 4)
        bar.setHeight(8)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TRACK))
        painter.drawRoundedRect(bar, 4, 4)
        fraction = index.data(Qt.ItemDataRole.UserRole)
        if fraction:
            bar.setWidth(max(5, bar.width() * fraction))
            painter.setBrush(QColor(ACTIVE))
            painter.drawRoundedRect(bar, 4, 4)
        painter.restore()


class DashboardPage(QWidget):
    scan_requested = Signal()
    downloads_requested = Signal()
    category_requested = Signal(str)
    browse_requested = Signal()
    review_requested = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        actions = QHBoxLayout()
        choose = FeedbackButton("Choose folder")
        choose.clicked.connect(self.scan_requested)
        self._scan_button = FeedbackButton("Scan Downloads")
        self._scan_button.clicked.connect(self.downloads_requested)
        self.review_button = FeedbackButton("Review moves")
        self.review_button.clicked.connect(self.review_requested)
        self.browse_button = FeedbackButton("Browse files")
        self.browse_button.clicked.connect(self.browse_requested)
        self.browse_button.setObjectName("PrimaryButton")
        self.browse_button.setEnabled(False)
        self.review_button.setEnabled(False)
        actions.addWidget(choose)
        actions.addWidget(self._scan_button)
        actions.addStretch()
        actions.addWidget(self.browse_button)
        actions.addWidget(self.review_button)
        layout.addLayout(actions)

        self._attempt = None
        self.run_panel = self._build_scan_summary()
        layout.addWidget(self.run_panel)

        self.graphs = InventoryGraphs()
        self.graphs.hide()
        layout.addWidget(self.graphs)

        self.inventory_panel = SurfaceCard()
        add_card_heading(self.inventory_panel.content_layout, "Completed inventory")
        self.inventory_details = detail_label()
        self.inventory_details.setFont(fixed_font())
        self.inventory_panel.content_layout.addWidget(self.inventory_details)
        self._inventory_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._inventory_layout.setSpacing(12)
        self.inventory_panel.content_layout.addLayout(self._inventory_layout)

        category_panel = SurfaceCard()
        add_card_heading(category_panel.content_layout, "Files by category")
        self.categories = self._tree(("CATEGORY", "FILES", "KNOWN SIZE", "TOP TYPES", "COUNT GRAPH"),
                                     "File counts by category")
        self.categories.headerItem().setToolTip(4, "Bars are scaled to the largest category.")
        self.categories.setItemDelegateForColumn(4, CountBars(self.categories))
        header = self.categories.header()
        header.setStretchLastSection(False)
        header.moveSection(4, 2)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        for column, width in enumerate((145, 64, 148, 87, 153)):
            self.categories.setColumnWidth(column, width)
        self.categories.setFixedHeight(155)
        self.categories.itemActivated.connect(self._browse_category)
        self.categories.itemClicked.connect(self._browse_category)
        category_panel.content_layout.addWidget(self.categories)

        path_panel = SurfaceCard()
        add_card_heading(path_panel.content_layout, "File tree")
        self._path_model = ScanPathModel(self)
        self.file_tree = ScanPathTree()
        self.file_tree.setModel(self._path_model)
        self.file_tree.setAccessibleName("Scanned folder tree")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setUniformRowHeights(True)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.file_tree.setFixedHeight(155)
        self.file_tree.setObjectName("InventoryTree")
        path_panel.content_layout.addWidget(self.file_tree)

        self._inventory_layout.addWidget(category_panel, 3)
        self._inventory_layout.addWidget(path_panel, 2)
        self.inventory_panel.hide()
        layout.addWidget(self.inventory_panel)
        layout.addStretch()

    def _build_scan_summary(self):
        card = SurfaceCard()
        card.setMinimumHeight(116)
        left = QWidget()
        overview = QVBoxLayout(left)
        overview.setContentsMargins(0, 0, 0, 0)
        overview.setSpacing(6)
        overview.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        title = QLabel("Latest scan attempt")
        title.setObjectName("CardTitle")
        self.scan_status = StatusBadge("Ready")
        self.scan_status.setProperty("scanSummary", True)
        title_row.addWidget(title)
        title_row.addWidget(self.scan_status)
        title_row.addStretch()
        overview.addLayout(title_row)
        self.run_details = detail_label("Choose a folder to begin a read-only scan.")
        self.run_timing = QLabel()
        self.run_timing.setObjectName("ScanTiming")
        self.run_timing.setWordWrap(True)
        self.run_error = detail_label()
        self.run_error.setObjectName("ScanError")
        for widget in (self.run_details, self.run_timing, self.run_error):
            overview.addWidget(widget)
        self.run_timing.hide()
        self.run_error.hide()

        right = QWidget()
        details = QVBoxLayout(right)
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(10)
        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.scan_artwork = ScanArtwork()
        self._metrics = {}
        for label, kind in (("Files found", "file"), ("Folders visited", "folder"),
                            ("Known size", "storage"), ("Warnings", "warning")):
            if self._metrics:
                stats.addWidget(divider(vertical=True))
            if kind == "folder":
                icon = self.scan_artwork
            else:
                icon = QLabel()
                icon.setPixmap(metric_icon(kind))
            text = QVBoxLayout()
            text.setSpacing(1)
            value = QLabel("—")
            value.setObjectName("ScanMetric")
            value.setAccessibleName(label)
            text.addWidget(QLabel(label))
            text.addWidget(value)
            tile = QWidget()
            contents = QHBoxLayout(tile)
            contents.setContentsMargins(6, 0, 2, 0)
            contents.setSpacing(9)
            contents.addWidget(icon)
            contents.addLayout(text, 1)
            stats.addWidget(tile, 1)
            self._metrics[label] = value
        details.addLayout(stats)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        progress_row.addWidget(QLabel("Metadata processed"))
        self.metadata_progress = ScanProgress(width=None, height=11)
        self.metadata_progress.setAccessibleName("Metadata files processed")
        self.metadata_progress.begin(1)
        progress_row.addWidget(self.metadata_progress, 1, Qt.AlignmentFlag.AlignVCenter)
        self.metadata_count = QLabel("—")
        self.metadata_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.metadata_count.setMinimumWidth(62)
        progress_row.addWidget(self.metadata_count)
        details.addLayout(progress_row)

        self._attempt_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._attempt_layout.setSpacing(16)
        self._attempt_layout.addWidget(left, 5)
        self._attempt_separator = divider(vertical=True)
        self._attempt_layout.addWidget(self._attempt_separator)
        self._attempt_layout.addWidget(right, 7)
        card.content_layout.addLayout(self._attempt_layout)
        self.warnings = self._tree(("STAGE", "PATH", "REASON"), "Scan warnings")
        self.warnings.setColumnWidth(0, 110)
        self.warnings.setColumnWidth(1, 260)
        self.warnings.hide()
        card.content_layout.addWidget(self.warnings)
        return card

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = (QBoxLayout.Direction.LeftToRight if event.size().width() >= 960
                     else QBoxLayout.Direction.TopToBottom)
        self._inventory_layout.setDirection(direction)
        self._attempt_layout.setDirection(direction)
        self._attempt_separator.setVisible(direction == QBoxLayout.Direction.LeftToRight)

    def _browse_category(self, item, _column):
        if item.data(0, Qt.ItemDataRole.UserRole):
            self.category_requested.emit(item.text(0))

    @staticmethod
    def _tree(headings, name):
        table = QTreeWidget()
        table.setHeaderLabels(headings)
        table.setAccessibleName(name)
        table.setRootIsDecorated(False)
        table.setUniformRowHeights(True)
        table.setAlternatingRowColors(True)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.setMinimumHeight(114)
        return table

    def show_attempt(self, attempt):
        finished = attempt.finished is not None
        if attempt is not self._attempt:
            self._attempt = attempt
            self._metrics["Known size"].setText("—")
            self.metadata_progress.begin()
        self._scan_button.setEnabled(finished)
        self.scan_artwork.set_busy(not finished)
        completed = attempt.status == "Completed"
        status = f"✓ {attempt.status}" if completed else attempt.status
        self.scan_status.set_status(status, muted=finished and not completed)
        self.run_details.setText(str(attempt.root))
        timing = f"Started    {attempt.started:%Y-%m-%d %H:%M:%S}"
        if finished:
            timing += (f"   ·   Finished    {attempt.finished:%Y-%m-%d %H:%M:%S}"
                       f"   ·   {attempt.elapsed:.1f} s elapsed")
        self.run_timing.setText(timing)
        self.run_timing.show()
        self.run_error.setText(attempt.error)
        self.run_error.setVisible(bool(attempt.error))
        self._metrics["Files found"].setText(f"{attempt.discovered:,}")
        self._metrics["Folders visited"].setText(f"{attempt.folders:,}")
        warning_count = len(attempt.discovery_issues) + len(attempt.metadata_issues)
        self._metrics["Warnings"].setText(f"{warning_count:,}")
        if finished or attempt.status == "Reading metadata" or self.metadata_progress.maximum():
            self.metadata_progress.report(attempt.processed, max(1, attempt.discovered))
            self.metadata_count.setText(f"{attempt.processed:,} / {attempt.discovered:,}")
        else:
            self.metadata_count.setText("—")
        if finished:
            self.warnings.clear()
            for stage, issues in (("Discovery", attempt.discovery_issues),
                                  ("Metadata", attempt.metadata_issues)):
                for issue in issues:
                    item = QTreeWidgetItem((stage, str(issue.path), issue.message))
                    item.setForeground(0, QColor(AMBER))
                    item.setToolTip(1, str(issue.path))
                    item.setToolTip(2, issue.message)
                    self.warnings.addTopLevelItem(item)
            self.warnings.setMaximumHeight(114 if warning_count < 4 else 176)
            self.warnings.setVisible(bool(warning_count))
        else:
            self.warnings.hide()

    def set_scan_result(self, directory, files, folders, finished, warning_count):
        groups = defaultdict(list)
        for item in files:
            groups[item.classification.category].append(item.metadata)
        sizes = [item.metadata.size_bytes for item in files if item.metadata.size_bytes is not None]
        total_size = sum(sizes)
        self._metrics["Known size"].setText(format_size(total_size if sizes or not files else None))
        self.inventory_details.setText(
            f"{directory}\n{finished:%Y-%m-%d %H:%M:%S} local   ·   "
            f"{len(files):,} files   ·   {folders:,} folders visited   ·   "
            f"{format_size(total_size)} known ({len(sizes):,}/{len(files):,} sizes)   ·   "
            f"{warning_count:,} warnings"
        )
        self.categories.clear()
        graph_totals = {}
        categories = sorted(KNOWN_CATEGORIES | groups.keys(),
                            key=lambda name: (-len(groups.get(name, ())), name))
        largest = max(map(len, groups.values()), default=1)
        for name in categories:
            items = groups.get(name, ())
            count = len(items)
            known = [item.size_bytes for item in items if item.size_bytes is not None]
            known_size = sum(known)
            if count:
                graph_totals[name] = count, known_size
            extensions = Counter(item.extension or "(no extension)" for item in items)
            types = ", ".join(f"{ext} ({n})" for ext, n in extensions.most_common(4))
            filled = max(1, round(count * 12 / largest)) if count else 0
            bar = "█" * filled + "░" * (12 - filled)
            size = f"{format_size(known_size)} ({len(known)}/{count})" if count else "—"
            row = QTreeWidgetItem((name, f"{count:,}", size, types or "—", bar))
            row.setData(0, Qt.ItemDataRole.UserRole, count)
            row.setData(4, Qt.ItemDataRole.UserRole, count / largest)
            row.setSizeHint(0, QSize(0, 27))
            row.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if files:
                row.setToolTip(4, f"{count:,} files · {count / len(files):.1%} of scanned files")
            row.setToolTip(3, ", ".join(f"{ext} ({n})" for ext, n in extensions.most_common()))
            self.categories.addTopLevelItem(row)
            row.setHidden(bool(files) and not count)
        self._path_model.set_paths(directory, (item.metadata.path for item in files))
        self.file_tree.expand(self._path_model.index(0, 0))
        self.graphs.show()
        self.graphs.set_totals(graph_totals)
        self.inventory_panel.show()
        self.browse_button.setEnabled(True)
        self.review_button.setEnabled(bool(files))
