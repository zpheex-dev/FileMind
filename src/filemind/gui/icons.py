"""Small, font-independent line icons for consistent desktop navigation."""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from filemind.gui.theme import ACTIVE, MUTED, PANEL


def metric_icon(kind):
    canvas = QPixmap(60, 60)
    canvas.setDevicePixelRatio(2)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(ACTIVE), 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    outline = QPainterPath()
    if kind == "file":
        outline.moveTo(7, 4)
        outline.lineTo(18, 4)
        outline.lineTo(24, 10)
        outline.lineTo(24, 26)
        outline.lineTo(7, 26)
        outline.closeSubpath()
        outline.moveTo(18, 4)
        outline.lineTo(18, 10)
        outline.lineTo(24, 10)
    elif kind == "storage":
        painter.drawEllipse(QRectF(4, 3, 22, 8))
        for y in (10, 17):
            painter.drawArc(QRectF(4, y, 22, 8), 180 * 16, 180 * 16)
        painter.drawLine(4, 7, 4, 21)
        painter.drawLine(26, 7, 26, 21)
    else:
        outline.moveTo(14, 4)
        outline.quadTo(15, 2, 16, 4)
        outline.lineTo(28, 24)
        outline.quadTo(29, 26, 26, 26)
        outline.lineTo(4, 26)
        outline.quadTo(1, 26, 2, 24)
        outline.closeSubpath()
        painter.drawLine(15, 11, 15, 18)
        painter.drawPoint(15, 22)
    painter.drawPath(outline)
    painter.end()
    return canvas


def navigation_icon(name: str) -> QIcon:
    canvas = QPixmap(40, 40)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    painter.setPen(QPen(QColor(MUTED), 1.3))
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
            painter.fillRect(QRectF(x - 2, y - 2, 4, 4), QColor(PANEL))
            painter.drawRect(QRectF(x - 2, y - 2, 4, 4))
    else:
        painter.drawLine(10, 2, 10, 18)
        painter.drawLine(2, 10, 18, 10)
        painter.drawLine(5, 5, 15, 15)
        painter.drawLine(5, 15, 15, 5)
        painter.drawEllipse(QRectF(7, 7, 6, 6))
    painter.end()
    return QIcon(canvas)
