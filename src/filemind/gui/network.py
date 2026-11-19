"""Interactive monochrome category map for the dashboard."""

import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from filemind.gui.theme import CYAN, PANEL, WINDOW
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
        self.terrain = QPixmap()

    def set_counts(self, counts):
        for button in self.nodes:
            button.hide()
            button.deleteLater()
        self.nodes.clear()
        self.scanned = True
        self.terrain = QPixmap()
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
        if self.terrain.size() != self.size():
            self.terrain = self._draw_terrain()
        painter.drawPixmap(0, 0, self.terrain)
        if not self.scanned:
            return
        center = QPointF(w / 2, h / 2)
        painter.setPen(QPen(QColor(CYAN), 1))
        for button in self.nodes:
            painter.drawLine(center, QPointF(button.geometry().center()))
        painter.setBrush(QColor(PANEL))
        painter.drawEllipse(center, 41, 41)
        painter.setPen(QPen(QColor("#e7eff6"), 2))
        painter.drawArc(QRectF(center.x()-46, center.y()-46, 92, 92), 17*16, 85*16)
        painter.drawText(QRectF(center.x()-42, center.y()-27, 84, 54), Qt.AlignCenter,
                         f"{self.total:,}\nfiles" if self.scanned else "No scan")


    def _draw_terrain(self):
        """Project a sampled relief surface into the canvas. Cache until resized."""
        width, height = self.width(), self.height()
        image = QPixmap(self.size())
        image.fill(QColor(WINDOW))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = min(width * .45, height * 1.17)
        cx = width * (.50 if self.scanned else .71)
        cy = height * .60
        for i in range(0, width, 24):
            painter.setPen(QColor("#122534"))
            painter.drawLine(i, 0, i, height)
        for j in range(0, height, 24):
            painter.drawLine(0, j, width, j)
        for j in range(62):
            y = j / 61 - .5
            points = []
            for i in range(102):
                x = i / 101 - .5
                ridge = .30 * math.exp(-((x+.12)**2*28+(y+.05)**2*18))
                ridge += .23 * math.exp(-((x-.23)**2*38+(y-.08)**2*26))
                ridge *= .85 + .15 * math.cos(17*x + 11*y)
                z = ridge + .016 * math.cos(23*x-19*y)
                points.append(QPointF(cx + scale * (1.23*x-.75*y),
                                      cy + scale * (.33*x+.55*y-z)))
            color = QColor("#55d6f0") if j % 8 == 0 else QColor("#29768c")
            color.setAlpha(95 if self.scanned else 185)
            painter.setPen(QPen(color, .8))
            painter.drawPolyline(QPolygonF(points))
            painter.setPen(QPen(QColor("#8deadf"), 1.6))
            painter.drawPoints(QPolygonF(points[j % 5::9]))
        painter.end()
        return image
