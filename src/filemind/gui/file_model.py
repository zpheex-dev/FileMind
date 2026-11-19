"""Virtual file table: values are computed only for visible cells."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


def format_size(size):
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


class FileTableModel(QAbstractTableModel):
    HEADERS = ("NAME", "TYPE", "SIZE", "MODIFIED", "CATEGORY", "RULE SCORE", "LOCATION")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []

    def set_files(self, files):
        self.beginResetModel()
        self.files = files
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.files)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        if role == Qt.ItemDataRole.ToolTipRole and section == 5:
            return "Heuristic rule strength, not a model probability."

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self.files[index.row()]
        metadata, decision = item.metadata, item.classification
        column = index.column()
        if role == Qt.ItemDataRole.ToolTipRole:
            return decision.explanation if column in (4, 5) else str(metadata.path)
        if role == Qt.ItemDataRole.UserRole:
            if column == 2:
                return metadata.size_bytes if metadata.size_bytes is not None else -1
            if column == 3:
                return metadata.modified_at_ns or 0
            if column == 5:
                return decision.confidence
            return str(self.data(index) or "").casefold()
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if column == 0:
            return metadata.name
        if column == 1:
            return metadata.extension[1:].upper() or "—"
        if column == 2:
            return format_size(metadata.size_bytes)
        if column == 3:
            return metadata.modified_at.strftime("%Y-%m-%d %H:%M") if metadata.modified_at else "—"
        if column == 4:
            return decision.category
        if column == 5:
            return f"{decision.confidence:.0%}"
        return str(metadata.path.parent)
