"""The most recent scan attempt and the inventory it has produced."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QBoxLayout, QHeaderView, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from filemind.categorizer.classifier import KNOWN_CATEGORIES
from filemind.gui.components import SurfaceCard, add_card_heading, detail_label
from filemind.gui.file_model import format_size
from filemind.gui.path_model import ScanPathModel, ScanPathTree
from filemind.gui.theme import ACTIVE, AMBER, MUTED
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
        layout.setSpacing(12)

        actions = QHBoxLayout()
        choose = QPushButton("Choose folder")
        choose.clicked.connect(self.scan_requested)
        self._scan_button = QPushButton("Scan Downloads")
        self._scan_button.clicked.connect(self.downloads_requested)
        self.review_button = QPushButton("Review moves")
        self.review_button.clicked.connect(self.review_requested)
        self.browse_button = QPushButton("Browse files")
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

        self.run_panel = SurfaceCard()
        add_card_heading(self.run_panel.content_layout, "LATEST SCAN ATTEMPT")
        self.run_details = detail_label("Choose a folder to begin a read-only scan.")
        self.run_panel.content_layout.addWidget(self.run_details)
        self.warnings = self._tree(("STAGE", "PATH", "REASON"), "Scan warnings")
        self.warnings.setColumnWidth(0, 110)
        self.warnings.setColumnWidth(1, 260)
        self.warnings.setMaximumHeight(176)
        self.warnings.hide()
        self.run_panel.content_layout.addWidget(self.warnings)
        layout.addWidget(self.run_panel)

        self.inventory_panel = SurfaceCard()
        add_card_heading(self.inventory_panel.content_layout, "COMPLETED INVENTORY")
        self.inventory_details = detail_label()
        self.inventory_panel.content_layout.addWidget(self.inventory_details)
        self._inventory_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._inventory_layout.setSpacing(12)
        self.inventory_panel.content_layout.addLayout(self._inventory_layout)

        category_panel = SurfaceCard()
        add_card_heading(category_panel.content_layout, "FILES BY CATEGORY")
        self.categories = self._tree(("CATEGORY", "FILES", "KNOWN SIZE", "TOP TYPES", "COUNT GRAPH"),
                                     "File counts by category")
        self.categories.headerItem().setToolTip(4, "Bars are scaled to the largest category.")
        header = self.categories.header()
        header.setStretchLastSection(False)
        header.moveSection(4, 2)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        for column, width in enumerate((125, 56, 124, 87, 121)):
            self.categories.setColumnWidth(column, width)
        self.categories.setMinimumHeight(356)
        self.categories.itemActivated.connect(self._browse_category)
        self.categories.itemClicked.connect(self._browse_category)
        category_panel.content_layout.addWidget(self.categories)

        path_panel = SurfaceCard()
        add_card_heading(path_panel.content_layout, "FILE TREE")
        self._path_model = ScanPathModel(self)
        self.file_tree = ScanPathTree()
        self.file_tree.setModel(self._path_model)
        self.file_tree.setAccessibleName("Scanned folder tree")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setUniformRowHeights(True)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.file_tree.setMinimumHeight(356)
        path_panel.content_layout.addWidget(self.file_tree)

        self._inventory_layout.addWidget(category_panel, 3)
        self._inventory_layout.addWidget(path_panel, 2)
        self.inventory_panel.hide()
        layout.addWidget(self.inventory_panel)
        layout.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = (QBoxLayout.Direction.LeftToRight if event.size().width() >= 960
                     else QBoxLayout.Direction.TopToBottom)
        self._inventory_layout.setDirection(direction)

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
        self._scan_button.setEnabled(attempt.finished is not None)
        lines = [f"{attempt.status.upper()}   ·   {attempt.root}",
                 f"Started    {attempt.started:%Y-%m-%d %H:%M:%S} local"]
        if attempt.finished:
            lines.append(f"Finished   {attempt.finished:%Y-%m-%d %H:%M:%S} local"
                         f"   ·   {attempt.elapsed:.1f} s elapsed")
        lines.extend((
            f"Discovery  {attempt.discovered:,} files found   ·   {attempt.folders:,} folders visited",
            f"Metadata   {attempt.processed:,} of {attempt.discovered:,} processed",
        ))
        if attempt.error:
            lines.append(attempt.error)
        self.run_details.setText("\n".join(lines))
        if attempt.finished:
            self.warnings.clear()
            for stage, issues in (("Discovery", attempt.discovery_issues),
                                  ("Metadata", attempt.metadata_issues)):
                for issue in issues:
                    item = QTreeWidgetItem((stage, str(issue.path), issue.message))
                    item.setForeground(0, QColor(AMBER))
                    item.setToolTip(1, str(issue.path))
                    item.setToolTip(2, issue.message)
                    self.warnings.addTopLevelItem(item)
            warning_count = self.warnings.topLevelItemCount()
            self.warnings.setMaximumHeight(114 if warning_count < 4 else 176)
            self.warnings.setVisible(bool(warning_count))
        else:
            self.warnings.hide()

    def set_scan_result(self, directory, files, folders, finished, warning_count):
        groups = defaultdict(list)
        for item in files:
            groups[item.classification.category].append(item.metadata)
        sizes = [item.metadata.size_bytes for item in files if item.metadata.size_bytes is not None]
        self.inventory_details.setText(
            f"{directory}\n{finished:%Y-%m-%d %H:%M:%S} local   ·   "
            f"{len(files):,} files   ·   {folders:,} folders visited\n"
            f"{format_size(sum(sizes))} known ({len(sizes):,}/{len(files):,} sizes)   ·   "
            f"{warning_count:,} warnings"
        )
        self.categories.clear()
        categories = sorted(KNOWN_CATEGORIES | groups.keys(),
                            key=lambda name: (-len(groups.get(name, ())), name))
        largest = max(map(len, groups.values()), default=1)
        for name in categories:
            items = groups.get(name, ())
            count = len(items)
            known = [item.size_bytes for item in items if item.size_bytes is not None]
            extensions = Counter(item.extension or "(no extension)" for item in items)
            types = ", ".join(f"{ext} ({n})" for ext, n in extensions.most_common(4))
            filled = max(1, round(count * 12 / largest)) if count else 0
            bar = "█" * filled + "░" * (12 - filled)
            size = f"{format_size(sum(known))} ({len(known)}/{count})" if count else "—"
            row = QTreeWidgetItem((name, f"{count:,}", size, types or "—", bar))
            row.setData(0, Qt.ItemDataRole.UserRole, count)
            row.setForeground(4, QColor(ACTIVE if count else MUTED))
            row.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if files:
                row.setToolTip(4, f"{count:,} files · {count / len(files):.1%} of scanned files")
            row.setToolTip(3, ", ".join(f"{ext} ({n})" for ext, n in extensions.most_common()))
            self.categories.addTopLevelItem(row)
        self._path_model.set_paths(directory, (item.metadata.path for item in files))
        self.file_tree.expand(self._path_model.index(0, 0))
        self.inventory_panel.show()
        self.browse_button.setEnabled(True)
        self.review_button.setEnabled(bool(files))
