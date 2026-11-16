"""PySide6 application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from filemind.gui.theme import APP_STYLESHEET
from filemind.gui.window import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("FileMind")
    application.setOrganizationName("FileMind")
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
