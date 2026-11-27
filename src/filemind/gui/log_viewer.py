"""Read saved activity logs inside the workspace."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout

from filemind.gui.components import detail_label, reveal
from filemind.gui.theme import fixed_font


class LogViewer(QDialog):
    def __init__(self, parent, title, paths):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(700, 500)
        self._paths = paths
        layout = QVBoxLayout(self)
        self.files = QComboBox()
        self.files.setAccessibleName("Saved activity logs")
        self.files.addItems([path.name for path in paths])
        self.files.setVisible(len(paths) > 1)
        layout.addWidget(self.files)
        self._path_label = detail_label()
        layout.addWidget(self._path_label)
        self.preview = QPlainTextEdit()
        self.preview.setAccessibleName("Log contents")
        self.preview.setFont(fixed_font())
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.files.currentIndexChanged.connect(self._show_file)
        self._show_file(self.files.currentIndex())

    def showEvent(self, event):
        super().showEvent(event)
        reveal(self.preview.viewport(), 180)

    def _show_file(self, index):
        if index < 0:
            self.preview.setPlainText("No activity logs have been saved yet.")
            return
        path = self._paths[index]
        self._path_label.setText(str(path))
        try:
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            contents = f"Could not read this log.\n{error}"
        self.preview.setPlainText(contents)
        reveal(self.preview.viewport(), 150)
