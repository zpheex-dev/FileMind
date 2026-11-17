"""PySide6 application entry point."""

import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont

from filemind.gui.theme import APP_STYLESHEET
from filemind.gui.window import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("FileMind")
    application.setOrganizationName("FileMind")
    application.setStyle("Fusion")
    application.setFont(QFont("Segoe UI" if sys.platform == "win32" else "DejaVu Sans", 9))
    application.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(1500, window.close)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
