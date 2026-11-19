from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, Signal

from filemind.organizer.planner import propose_organization


class PlanWorker(QThread):
    ready = Signal(int, object, str)

    def __init__(self, generation, directory, files, folders, parent):
        super().__init__(parent)
        self.args = directory, files, folders
        self.generation = generation

    def run(self):
        try:
            rows = propose_organization(*self.args)
        except (OSError, ValueError) as error:
            self.ready.emit(self.generation, (), str(error))
        else:
            self.ready.emit(self.generation, rows, "")


class ProposalModel(QAbstractTableModel):
    headings = ("Current location", "Proposed destination", "Reason", "Conflict status")

    def __init__(self, parent):
        super().__init__(parent)
        self.rows = ()
        self.unchecked = set()
        self.directory = None

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headings)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.headings[section]
        return super().headerData(section, orientation, role)

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and index.column() == 0 and not self.rows[index.row()].has_conflict:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def data(self, index, role):
        if not index.isValid():
            return
        row = self.rows[index.row()]
        if role == Qt.CheckStateRole and index.column() == 0:
            return Qt.Unchecked if row.has_conflict or row.current_path in self.unchecked else Qt.Checked
        if role == Qt.DisplayRole and self.directory is not None and index.column() < 2:
            path = (row.current_path, row.destination)[index.column()]
            return str(path.relative_to(self.directory))
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return (str(row.current_path), str(row.destination), row.reason,
                    "; ".join(row.conflicts) or "No conflict detected")[index.column()]

    def setData(self, index, value, role):
        if role != Qt.CheckStateRole or not (self.flags(index) & Qt.ItemIsUserCheckable):
            return False
        path = self.rows[index.row()].current_path
        if Qt.CheckState(value) == Qt.Checked:
            self.unchecked.discard(path)
        else:
            self.unchecked.add(path)
        self.dataChanged.emit(index, index, [role])
        return True
