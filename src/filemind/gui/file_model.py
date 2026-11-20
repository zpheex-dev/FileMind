"""Virtual inventory table with bulk sorting and filtering."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


def format_size(size):
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


def _display_value(item, column):
    metadata, decision = item.metadata, item.classification
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


def _sort_key(item, column):
    metadata = item.metadata
    if column == 2:
        return metadata.size_bytes if metadata.size_bytes is not None else -1
    if column == 3:
        return metadata.modified_at_ns or 0
    if column == 5:
        return item.classification.confidence
    return _display_value(item, column).casefold()


class FileTableModel(QAbstractTableModel):
    HEADERS = ("NAME", "TYPE", "SIZE", "MODIFIED", "CATEGORY", "RULE SCORE", "LOCATION")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []
        self._column = 0
        self._order = Qt.SortOrder.AscendingOrder

    def set_files(self, files, query=""):
        if query:
            files = [item for item in files if any(
                query in _display_value(item, column).casefold()
                for column in range(len(self.HEADERS))
            )]
        self.beginResetModel()
        self.files = sorted(files, key=lambda item: _sort_key(item, self._column),
                            reverse=self._order == Qt.SortOrder.DescendingOrder)
        self.endResetModel()

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if column < 0 or (column, order) == (self._column, self._order):
            return
        self._column, self._order = column, order
        self.layoutAboutToBeChanged.emit()
        before = self.persistentIndexList()
        ordered = sorted(enumerate(self.files), key=lambda entry: _sort_key(entry[1], column),
                         reverse=order == Qt.SortOrder.DescendingOrder)
        self.files = [item for _, item in ordered]
        positions = {old: new for new, (old, _) in enumerate(ordered)}
        after = [self.index(positions[index.row()], index.column()) for index in before]
        self.changePersistentIndexList(before, after)
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.files)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self.files[index.row()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return item.classification.explanation if index.column() in (4, 5) else str(item.metadata.path)
        if role == Qt.ItemDataRole.DisplayRole:
            return _display_value(item, index.column())
