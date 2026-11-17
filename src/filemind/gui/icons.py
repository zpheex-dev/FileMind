"""Small, font-independent line icons for consistent desktop navigation."""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def navigation_icon(name: str) -> QIcon:
    canvas = QPixmap(40, 40)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    painter.setPen(QPen(QColor("#70b8b5"), 1.3))
    if name == "Dashboard":
        for x, y in ((3, 3), (11, 3), (3, 11), (11, 11)):
            painter.drawRoundedRect(QRectF(x, y, 5, 5), 1, 1)
    elif name == "My Files":
        painter.drawRoundedRect(QRectF(3, 4, 14, 13), 1, 1)
        for y in (8, 11, 14):
            painter.drawLine(6, y, 14, y)
    elif name == "Duplicate Finder":
        painter.drawRoundedRect(QRectF(3, 3, 10, 11), 1, 1)
        painter.drawRoundedRect(QRectF(7, 7, 10, 11), 1, 1)
    elif name == "Activity History":
        painter.drawEllipse(QRectF(3, 3, 14, 14))
        painter.drawLine(10, 5, 10, 10)
        painter.drawLine(10, 10, 14, 12)
    elif name == "Settings":
        for x, y in ((5, 7), (10, 13), (15, 8)):
            painter.drawLine(x, 3, x, 17)
            painter.fillRect(QRectF(x - 2, y - 2, 4, 4), QColor("#10141b"))
            painter.drawRect(QRectF(x - 2, y - 2, 4, 4))
    else:
        painter.drawLine(10, 2, 10, 18)
        painter.drawLine(2, 10, 18, 10)
        painter.drawLine(5, 5, 15, 15)
        painter.drawLine(5, 15, 15, 5)
        painter.drawEllipse(QRectF(7, 7, 6, 6))
    painter.end()
    return QIcon(canvas)
