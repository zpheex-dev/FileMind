"""Paint transient feedback without moving layout-managed widgets."""

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QProgressBar, QWidget

from filemind.gui.theme import ACTIVE, BORDER, TRACK


def can_animate(widget):
    if not widget.isVisible():
        return False
    window = widget.window()
    while window is not None:
        if getattr(window, "reduce_motion", False):
            return False
        parent = window.parentWidget()
        window = parent.window() if parent is not None else None
    return True


def tween(parent, duration, easing=QEasingCurve.Type.OutCubic):
    animation = QVariantAnimation(parent)
    animation.setDuration(duration)
    animation.setEasingCurve(easing)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    return animation


class SnapshotTransition(QWidget):
    """Move a short-lived visual copy while the new content is already interactive."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._snapshot = QPixmap()
        self._animation = tween(self, 240)
        self._animation.valueChanged.connect(lambda _: self.update())
        self._animation.finished.connect(self.clear)
        self.hide()

    def play(self, snapshot, start, end, *, soften=False):
        self.clear()
        if snapshot.isNull() or not can_animate(self.parentWidget()):
            return
        area = start.united(end).toAlignedRect().intersected(self.parentWidget().rect())
        if area.isEmpty():
            return
        self.setGeometry(area)
        offset = area.topLeft()
        self._start = start.translated(-offset)
        self._end = end.translated(-offset)
        self._snapshot = snapshot
        # Filter a cached, smaller copy for the outgoing page's defocus.
        self._soft = (snapshot.scaled(max(1, snapshot.width() // 4),
                                      max(1, snapshot.height() // 4),
                                      mode=Qt.TransformationMode.SmoothTransformation)
                      if soften else QPixmap())
        self.raise_()
        self.show()
        self._animation.start()

    def clear(self):
        self._animation.stop()
        self.hide()
        self._snapshot = QPixmap()
        self._soft = QPixmap()

    def paintEvent(self, event):
        if self._snapshot.isNull():
            return
        phase = self._animation.currentValue()
        target = QRectF(
            self._start.topLeft() + (self._end.topLeft() - self._start.topLeft()) * phase,
            self._start.size() + (self._end.size() - self._start.size()) * phase,
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(1 - phase)
        pixmap = self._soft if not self._soft.isNull() else self._snapshot
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))


class ScanProgress(QProgressBar):
    """Glide between measured values and sweep while totals are unknown."""

    def __init__(self, width=110, height=8):
        super().__init__()
        self.setAccessibleName("Workspace scan progress")
        self.setTextVisible(False)
        if width is not None:
            self.setFixedWidth(width)
        self.setFixedHeight(height)
        self._sweep = tween(self, 1250, QEasingCurve.Type.Linear)
        self._sweep.setLoopCount(-1)
        self._fill = tween(self, 170)
        for animation in (self._sweep, self._fill):
            animation.valueChanged.connect(lambda _: self.update())
        self.hide()

    def begin(self, maximum=0):
        self._fill.stop()
        self.setRange(0, maximum)
        self.setValue(0)
        self._fill.setStartValue(0.0)
        self._fill.setEndValue(0.0)
        self.show()
        self.refresh_motion()

    def report(self, value, maximum):
        if self.maximum() == maximum and self.value() == value:
            return
        was_busy = self.maximum() == 0
        previous = 0.0 if was_busy else self._fill.currentValue()
        if self.maximum() != maximum:
            self.setRange(0, maximum)
            self.refresh_motion()
        self.setValue(value)
        self._fill.stop()
        self._fill.setStartValue(previous)
        self._fill.setEndValue(value / maximum)
        if can_animate(self):
            self._fill.start()
        else:
            self._fill.setCurrentTime(self._fill.duration())
        self.update()

    def refresh_motion(self):
        if self.maximum() == 0 and can_animate(self):
            self._sweep.start()
        else:
            self._sweep.stop()
        if not can_animate(self):
            self._fill.stop()
            self._fill.setCurrentTime(self._fill.duration())
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_motion()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sweep.stop()
        self._fill.stop()
        self._fill.setCurrentTime(self._fill.duration())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        bounds = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        track = QPainterPath()
        radius = bounds.height() / 2
        track.addRoundedRect(bounds, radius, radius)
        painter.fillPath(track, QColor(TRACK))
        painter.setClipPath(track)
        if self.maximum() == 0:
            phase = self._sweep.currentValue()
            if not can_animate(self):
                phase = 0.5
            width = bounds.width() * 0.48
            left = phase * (bounds.width() + width) - width
            beam = QRectF(left, 0, width, bounds.height())
            gradient = QLinearGradient(beam.topLeft(), beam.topRight())
            gradient.setColorAt(0, QColor(TRACK))
            gradient.setColorAt(0.58, QColor(ACTIVE))
            gradient.setColorAt(1, QColor(TRACK))
            painter.fillRect(beam, gradient)
        else:
            fill = (self._fill.currentValue() if can_animate(self)
                    else max(0, self.value()) / self.maximum())
            bounds.setWidth(bounds.width() * fill)
            gradient = QLinearGradient(bounds.topLeft(), bounds.topRight())
            gradient.setColorAt(0, QColor("#7bebc7"))
            gradient.setColorAt(1, QColor(ACTIVE))
            painter.setBrush(gradient)
            painter.drawRoundedRect(bounds, radius, radius)
