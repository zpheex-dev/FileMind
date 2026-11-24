"""Activity History table and background journal operations."""

from collections import Counter

from filemind.gui.components import FeedbackButton, SurfaceCard, add_card_heading, detail_label, reveal
from filemind.gui.theme import SUCCESS, AMBER
from PySide6.QtGui import QColor
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QTableView, QVBoxLayout, QWidget


class JournalWorker(QThread):
    def __init__(self, journal, action, args, parent):
        super().__init__(parent)
        self.journal, self.action, self.args = journal, action, args
        self.batch = None
        self.error = ""
        self.rows = []

    def run(self):
        try:
            self.batch = getattr(self.journal, self.action)(*self.args)
            self.rows = self.journal.history()
        except Exception as error:
            self.error = str(error)


class HistoryModel(QAbstractTableModel):
    columns = (("created", "Time (UTC)"), ("original", "Original path"), ("destination", "Destination"),
               ("status", "Status"), ("reason", "Details"))

    def __init__(self, parent):
        super().__init__(parent)
        self.rows = []

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.columns)

    def data(self, index, role):
        if index.isValid() and index.column() == 3 and role == Qt.ForegroundRole:
            row = self.rows[index.row()]
            if row["reason"] or row["status"] in {"skipped", "ambiguous"}:
                return QColor(AMBER)
            if row["status"] in {"moved", "copied", "undone"}:
                return QColor(SUCCESS)
        if index.isValid() and role in (Qt.DisplayRole, Qt.ToolTipRole):
            return self.rows[index.row()][self.columns[index.column()][0]]

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section][1]
        return super().headerData(section, orientation, role)


class ActivityHistoryPage(QWidget):
    undo_requested = Signal(object)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        panel = SurfaceCard()
        layout.addWidget(panel)
        add_card_heading(panel.content_layout, "OPERATION HISTORY")
        self.summary = QLabel("No operations recorded.")
        self.summary.setWordWrap(True)
        panel.content_layout.addWidget(self.summary)
        self.model = HistoryModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for column, width in enumerate((175, 260, 260, 95)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().moveSection(3, 1)
        self.table.hideColumn(4)
        self.table.setMinimumHeight(220)
        panel.content_layout.addWidget(self.table, 1)
        self.details = detail_label("Select an operation to inspect the paths and outcome.")
        panel.content_layout.addWidget(self.details)
        footer = QHBoxLayout()
        footer.addWidget(QLabel("Select completed copies or moves to undo"), 1)
        self.button = FeedbackButton("Undo selected operations")
        self.button.setEnabled(False)
        self.table.selectionModel().selectionChanged.connect(self._update_button)
        self.table.selectionModel().currentRowChanged.connect(self._show_details)
        self.button.clicked.connect(lambda: self.undo_requested.emit(self.selected_ids()))
        self.button.setObjectName("ReviewButton")
        footer.addWidget(self.button)
        panel.content_layout.addLayout(footer)

    def _show_details(self, current, _previous=None):
        if not current.isValid():
            self.details.setText("Select an operation to inspect the paths and outcome.")
            return
        row = self.model.rows[current.row()]
        reason = f"\nReason  {row['reason']}" if row["reason"] else ""
        self.details.setText(
            f"{row['status'].upper()}  ·  {row['created']} UTC{reason}\n"
            f"From  {row['original']}\nTo    {row['destination']}"
        )

    def selected_ids(self):
        rows = (self.model.rows[i.row()] for i in self.table.selectionModel().selectedRows())
        return [r["id"] for r in rows if r["status"] in ("moved", "copied")]

    def _update_button(self):
        count = len(self.selected_ids())
        self.button.setEnabled(bool(count))
        self.button.setText(f"Undo {count:,} operations" if count else "Undo selected operations")

    def show_rows(self, rows, batch=None, undo_ids=()):
        self.model.replace(rows)
        latest_batch = batch if batch is not None else (rows[0]["batch"] if rows else None)
        undo_ids = set(undo_ids)
        batch_rows = []
        selection = QItemSelection()
        focus = QModelIndex()
        for index, row in enumerate(rows):
            in_report = row["id"] in undo_ids if undo_ids else row["batch"] == latest_batch
            if not in_report:
                continue
            batch_rows.append(row)
            cell = self.model.index(index, 0)
            if not focus.isValid():
                focus = cell
            if row["status"] in ("moved", "copied"):
                selection.select(cell, cell)
        selected = self.table.selectionModel()
        selected.select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        selected.setCurrentIndex(focus, QItemSelectionModel.NoUpdate)
        if focus.isValid():
            self.table.scrollTo(focus)
        self._show_details(focus)
        self._update_button()
        if batch_rows:
            counts = Counter(
                "blocked" if undo_ids and row["status"] in ("moved", "copied") else row["status"]
                for row in batch_rows
            )
            outcome = "  ·  ".join(f"{count:,} {status}" for status, count in sorted(counts.items()))
            label = "Undo outcome" if undo_ids else "Latest batch"
            self.summary.setText(f"{label}  ·  {outcome}    |    {len(rows):,} operations")
        else:
            self.summary.setText("Confirmed moves appear here. Select moved files to undo.")
        if batch is not None or undo_ids:
            reveal(self.summary, 180)
