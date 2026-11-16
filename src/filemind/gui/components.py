"""Reusable widgets shared by FileMind pages."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SurfaceCard(QFrame):
    """A consistently styled panel for page content."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SurfaceCard")
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(20, 18, 20, 18)
        self.content_layout.setSpacing(12)


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


class MetricCard(SurfaceCard):
    """A dashboard metric that can display an explicit empty value."""

    def __init__(self, label: str, value: str, note: str) -> None:
        super().__init__()
        self.content_layout.setSpacing(7)

        label_widget = QLabel(label.upper())
        label_widget.setObjectName("MetricLabel")
        self.value_widget = QLabel(value)
        self.value_widget.setObjectName("MetricValue")
        self.note_widget = QLabel(note)
        self.note_widget.setObjectName("MutedText")

        self.content_layout.addWidget(label_widget)
        self.content_layout.addWidget(self.value_widget)
        self.content_layout.addWidget(self.note_widget)

    def set_value(self, value: str, note: str) -> None:
        self.value_widget.setText(value)
        self.note_widget.setText(note)


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


def add_status_row(
    layout: QHBoxLayout,
    text: str,
    muted: bool = False,
) -> StatusBadge:
    """Add a workflow badge at the end of a horizontal row."""
    badge = StatusBadge(text, muted)
    layout.addWidget(badge)
    return badge
