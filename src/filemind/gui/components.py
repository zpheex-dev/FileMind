"""Reusable widgets shared by FileMind pages."""

from math import cos, sin, tau

from PySide6.QtCore import QEvent, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)
from filemind.gui.icons import navigation_icon
from filemind.gui.motion import can_animate, tween
from filemind.gui.theme import ACTIVE, AMBER


class SurfaceCard(QFrame):
    """A consistently styled panel for page content."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SurfaceCard")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(14, 12, 14, 12)
        self.content_layout.setSpacing(9)


def divider(*, vertical=False):
    line = QFrame()
    line.setObjectName("CardDivider")
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    return line


class CardTitle(QWidget):
    """A compact title and optional description for a card."""

    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        layout.addWidget(title_label)

        if description:
            description_label = QLabel(description)
            description_label.setObjectName("MutedText")
            description_label.setWordWrap(True)
            layout.addWidget(description_label)


class EmptyState(QWidget):
    """An explanatory message for a view that has no data yet."""

    def __init__(
        self,
        title: str,
        description: str,
        icon: str = "·",
        action_text: str | None = None,
        action_enabled: bool = False,
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon_label = QLabel(icon)
        icon_label.setPixmap(navigation_icon("My Files").pixmap(26, 26))
        icon_label.setObjectName("EmptyIcon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("EmptyTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label = QLabel(description)
        self.description_label.setObjectName("EmptyDescription")
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setWordWrap(True)

        layout.addWidget(icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)

        if action_text:
            button = FeedbackButton(action_text)
            button.setObjectName("SecondaryButton")
            button.setEnabled(action_enabled)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)

    def set_message(self, title: str, description: str) -> None:
        self.title_label.setText(title)
        self.description_label.setText(description)


class StatusBadge(QLabel):
    """A small label for a workflow state."""

    def __init__(self, text: str, muted: bool = False) -> None:
        super().__init__(text)
        self.setObjectName("StatusBadgeMuted" if muted else "StatusBadge")
        self._burst = tween(self, 680, QEasingCurve.Type.OutQuad)
        self._burst.valueChanged.connect(lambda _: self.update())

    def celebrate(self):
        if can_animate(self):
            self._burst.stop()
            self._burst.start()

    def set_status(self, text, muted):
        style_name = "StatusBadgeMuted" if muted else "StatusBadge"
        if text == self.text() and style_name == self.objectName():
            return
        self._burst.stop()
        self.setText(text)
        if style_name != self.objectName():
            self.setObjectName(style_name)
            self.style().unpolish(self)
            self.style().polish(self)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not can_animate(self) or self._burst.state() != self._burst.State.Running:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        phase = self._burst.currentValue()
        painter.setOpacity(1 - phase)
        colors = (ACTIVE, AMBER, "#d5fae9", "#7bbafa")
        # Send the particles around the sides of the label, clear of its text.
        for index in range(12):
            angle = tau * index / 6
            center = QPointF(5 if index < 6 else self.width() - 5, self.height() / 2)
            painter.save()
            painter.translate(center + QPointF(cos(angle) * 5 * phase, sin(angle) * 11 * phase))
            painter.rotate(index * 41 + phase * 80)
            painter.setBrush(QColor(colors[index % len(colors)]))
            painter.drawRoundedRect(QRectF(-1.4, -2.1, 2.8, 4.2), 0.7, 0.7)
            painter.restore()


def add_card_heading(
    layout: QVBoxLayout,
    title: str,
    description: str = "",
) -> None:
    """Add the standard heading block to a card layout."""
    layout.addWidget(CardTitle(title, description))


def detail_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse |
                                  Qt.TextInteractionFlag.TextSelectableByKeyboard)
    return label


def reveal(widget, duration, initial_opacity=0.6):
    if not can_animate(widget):
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(initial_opacity)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", effect)
    animation.setDuration(duration)
    animation.setStartValue(initial_opacity)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda: effect.setEnabled(False))
    animation.start()


class FeedbackButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._pointer = None
        self._hover = tween(self, 170)
        self._press = tween(self, 90)
        for animation in (self._hover, self._press):
            animation.setEndValue(0.0)
            animation.valueChanged.connect(lambda _: self.update())
        self.pressed.connect(lambda: self._press_to(1.0))
        self.released.connect(lambda: self._press_to(0.0))

    def _press_to(self, depth):
        self._press.setDuration(80 if depth else 250)
        self._press.setEasingCurve(QEasingCurve.Type.OutCubic if depth else QEasingCurve.Type.OutBack)
        self._animate_to(self._press, depth)

    def _animate_to(self, animation, value):
        animation.stop()
        animation.setStartValue(animation.currentValue())
        animation.setEndValue(value)
        if self.isEnabled() and can_animate(self):
            animation.start()
        else:
            animation.setCurrentTime(animation.duration())

    def enterEvent(self, event):
        super().enterEvent(event)
        self._pointer = event.position()
        self._animate_to(self._hover, 1.0)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._animate_to(self._hover, 0.0)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._pointer = event.position()
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange and hasattr(self, "_press"):
            self._animate_to(self._hover, float(self.underMouse() and self.isEnabled()))
            self._animate_to(self._press, 0.0)

    def paintEvent(self, event):
        if not self.isEnabled() or not can_animate(self):
            super().paintEvent(event)
            return
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.state &= ~QStyle.StateFlag.State_MouseOver
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QRectF(self.rect()).center()
        painter.translate(center)
        scale = 1.0 - self._press.currentValue() * 0.038
        painter.scale(scale, scale)
        painter.translate(-center)
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)
        strength = self._hover.currentValue()
        if strength > 0:
            inset = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            clip = QPainterPath()
            clip.addRoundedRect(inset, 7, 7)
            painter.setClipPath(clip)
            pointer = self._pointer if self._pointer is not None else center
            light = QRadialGradient(center + (pointer - center) * 0.65, self.width() * 0.75)
            color = QColor("#ffffff" if self.objectName() == "PrimaryButton" else ACTIVE)
            color.setAlphaF(0.22 * strength)
            light.setColorAt(0, color)
            color.setAlphaF(0.035 * strength)
            light.setColorAt(1, color)
            painter.fillRect(inset, light)
