"""Activity History table and background journal operations."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal
from PySide6.QtWidgets import QAbstractItemView, QLabel, QPushButton, QTableView, QVBoxLayout, QWidget


class JournalWorker(QThread):
    def __init__(self, journal, action, args, parent):
        super().__init__(parent)
        self.journal, self.action, self.args = journal, action, args
        self.error = ""
        self.rows = []

    def run(self):
        try:
            getattr(self.journal, self.action)(*self.args)
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
        layout.addWidget(self.summary)
        self.model = HistoryModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setDefaultSectionSize(205)
        layout.addWidget(self.table)
        self.button = QPushButton("Undo selected moves")
        self.button.setEnabled(False)
        self.table.selectionModel().selectionChanged.connect(self._update_button)
        self.button.clicked.connect(lambda: self.undo_requested.emit(self.selected_ids()))
        layout.addWidget(self.button)

    def selected_ids(self):
        rows = (self.model.rows[i.row()] for i in self.table.selectionModel().selectedRows())
        return [r["id"] for r in rows if r["status"] == "moved"]

    def _update_button(self):
        self.button.setEnabled(bool(self.selected_ids()))

    def show_rows(self, rows):
        self.model.replace(rows)
        self._update_button()
        self.summary.setText(f"{len(rows):,} file operations. Select moved files to undo." if rows
                             else "No operations recorded.")
