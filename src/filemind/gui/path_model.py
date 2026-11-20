"""A read-only tree of paths from the completed scan."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QTreeView

from filemind.gui.theme import BORDER


@dataclass(slots=True, eq=False)
class PathNode:
    path: Path
    parent: "PathNode | None"
    children: list["PathNode"] | None = None
    row: int = 0


class ScanPathModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = None

    def set_paths(self, directory, paths):
        root = PathNode(directory, None, [])
        folders = {directory: root}
        for path in paths:
            if not path.is_relative_to(directory):
                continue
            missing = []
            folder = path.parent
            while folder not in folders:
                missing.append(folder)
                folder = folder.parent
            parent = folders[folder]
            for folder in reversed(missing):
                node = PathNode(folder, parent, [])
                parent.children.append(node)
                folders[folder] = node
                parent = node
            parent.children.append(PathNode(path, parent))

        for node in folders.values():
            node.children.sort(key=lambda child: (child.children is None,
                                                  child.path.name.casefold(), child.path.name))
            for row, child in enumerate(node.children):
                child.row = row
        self.beginResetModel()
        self._root = root
        self.endResetModel()

    def columnCount(self, _parent=QModelIndex()):
        return 1

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            return int(self._root is not None)
        return len(parent.internalPointer().children or ())

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        node = parent.internalPointer().children[row] if parent.isValid() else self._root
        return self.createIndex(row, column, node)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        parent = index.internalPointer().parent
        return self.createIndex(parent.row, 0, parent) if parent is not None else QModelIndex()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            name = node.path.name or str(node.path)
            return name + "/" if node.children is not None and node.path.name else name
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(node.path)


class ScanPathTree(QTreeView):
    """Keep native expand controls and draw the terminal-style branch guides."""

    def drawBranches(self, painter, rect, index):
        super().drawBranches(painter, rect, index)
        if not index.parent().isValid():
            return

        painter.save()
        painter.setPen(QPen(QColor(BORDER)))
        model = self.model()
        indent = self.indentation()
        step = -indent if self.layoutDirection() == Qt.LayoutDirection.LeftToRight else indent
        edge = rect.right() if step < 0 else rect.left()
        x = edge + step // 2
        middle = rect.center().y()
        branch = model.hasChildren(index)
        gap = 5 if branch else 0
        painter.drawLine(x, rect.top(), x, middle - gap)
        if index.row() + 1 < model.rowCount(index.parent()):
            painter.drawLine(x, middle + gap, x, rect.bottom())
        painter.drawLine(x + (gap if step < 0 else -gap), middle, edge, middle)

        ancestor = index.parent()
        while ancestor.parent().isValid():
            x += step
            if ancestor.row() + 1 < model.rowCount(ancestor.parent()):
                painter.drawLine(x, rect.top(), x, rect.bottom())
            ancestor = ancestor.parent()
        painter.restore()
