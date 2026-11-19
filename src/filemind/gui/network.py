"""Interactive monochrome category map for the dashboard."""

import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget


class FileMap(QWidget):
    category_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(230)
        self.setAccessibleName("File map")
        self.nodes = []
        self.total = 0
        self.scanned = False

    def set_counts(self, counts):
        for button in self.nodes:
            button.hide()
            button.deleteLater()
        self.nodes.clear()
        self.scanned = True
        self.total = sum(counts.values())
        for category, count in counts.most_common():
            button = QPushButton(f"{category}   {count:,}", self)
            button.setObjectName("MapNode")
            button.setToolTip(f"Browse {count:,} files in {category}")
            button.clicked.connect(lambda checked=False, name=category: self.category_requested.emit(name))
            button.adjustSize()
            button.show()
            self.nodes.append(button)
        self.setMinimumHeight(max(230, ((len(self.nodes) + 1) // 2) * 45 + 42))
        self._place_nodes()
        self.update()

    def _place_nodes(self):
        for index, button in enumerate(self.nodes):
            side = index % 2
            rows = (len(self.nodes) + 1 - side) // 2
            fraction = (index // 2 + .5) / rows
            x = self.width() * (.23 if side == 0 else .77)
            button.move(round(x - button.width() / 2), round(16 + fraction * (self.height() - 32) - button.height() / 2))

    def resizeEvent(self, event):
        self._place_nodes()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor("#101010"))
        # An original wire mesh gives the empty map a spatial reference.
        previous = []
        for row in range(9):
            points = []
            for column in range(21):
                x = w * column / 20
                wave = math.sin(column * .47 + row * .32) * math.cos(row * .34)
                points.append(QPointF(x, h * (.12 + row * .097 + .105 * wave)))
            painter.setPen(QPen(QColor("#292929"), .8))
            for col, point in enumerate(points):
                if col:
                    painter.drawLine(points[col - 1], point)
                if previous:
                    painter.drawLine(previous[col], point)
                    if col and (col + row) % 2 == 0:
                        painter.drawLine(previous[col - 1], point)
            previous = points
        center = QPointF(w / 2, h / 2)
        painter.setPen(QPen(QColor("#a2a2a2"), 1))
        for button in self.nodes:
            painter.drawLine(center, QPointF(button.geometry().center()))
        painter.setBrush(QColor("#101010"))
        painter.drawEllipse(center, 41, 41)
        painter.setPen(QPen(QColor("#fafafa"), 2))
        painter.drawArc(QRectF(center.x()-46, center.y()-46, 92, 92), 17*16, 85*16)
        painter.drawText(QRectF(center.x()-42, center.y()-27, 84, 54), Qt.AlignCenter,
                         f"{self.total:,}\nfiles" if self.scanned else "No scan")
