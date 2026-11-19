"""Activity History table and background journal operations."""

from filemind.gui.theme import SUCCESS, ERROR, AMBER
from PySide6.QtGui import QColor
from PySide6.QtCore import QItemSelection, QItemSelectionModel, QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QPushButton, QTableView, QVBoxLayout, QWidget


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
            return QColor(ERROR if row["reason"] else SUCCESS if row["status"] == "moved" else AMBER)
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
        self.summary = QLabel("No operations recorded.")
        bar = QHBoxLayout()
        bar.addWidget(self.summary, 1)
        self.summary.setWordWrap(True)
        layout.addLayout(bar)
        self.model = HistoryModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setDefaultSectionSize(205)
        layout.addWidget(self.table)
        self.button = QPushButton("Undo selected moves")
        self.button.setEnabled(False)
        self.table.selectionModel().selectionChanged.connect(self._update_button)
        self.button.clicked.connect(lambda: self.undo_requested.emit(self.selected_ids()))
        self.button.setObjectName("ReviewButton")
        bar.addWidget(self.button)

    def selected_ids(self):
        rows = (self.model.rows[i.row()] for i in self.table.selectionModel().selectedRows())
        return [r["id"] for r in rows if r["status"] == "moved"]

    def _update_button(self):
        count = len(self.selected_ids())
        self.button.setEnabled(bool(count))
        self.button.setText(f"Undo selected moves ({count:,})" if count else "Undo selected moves")

    def show_rows(self, rows, batch=None):
        self.model.replace(rows)
        if batch is None and rows:
            batch = rows[0]["batch"]
        selection = QItemSelection()
        for index, row in enumerate(rows):
            if row["batch"] == batch and row["status"] == "moved":
                cell = self.model.index(index, 0)
                selection.select(cell, cell)
        self.table.selectionModel().select(selection, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        self._update_button()
        self.summary.setText(f"{len(rows):,} file operations. Select moved files to undo." if rows
                             else "Confirmed moves appear here. Select a moved file to undo it.")
