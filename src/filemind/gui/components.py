"""Reusable widgets shared by FileMind pages."""

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from filemind.gui.icons import navigation_icon


class SurfaceCard(QFrame):
    """A consistently styled panel for page content."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SurfaceCard")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(12, 10, 12, 10)
        self.content_layout.setSpacing(8)


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
            button = QPushButton(action_text)
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

def reveal(widget, duration, initial_opacity=0.72):
    if not widget.isVisible() or getattr(widget.window(), "reduce_motion", False):
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(initial_opacity)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", effect)
    animation.setDuration(duration)
    animation.setStartValue(initial_opacity)
    animation.setEndValue(1.0)
    animation.finished.connect(lambda: widget.setGraphicsEffect(None))
    animation.start()


class FeedbackButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.pressed.connect(lambda: reveal(self, 100, 0.86))
