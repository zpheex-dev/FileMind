"""PySide6 application entry point."""

import sys
from importlib.resources import files

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon

from filemind.gui.theme import APP_STYLESHEET
from filemind.gui.window import MainWindow


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("FileMind")
    application.setDesktopFileName("dev.zpheex.FileMind")
    application.setWindowIcon(QIcon(str(files("filemind.gui").joinpath("assets", "filemind.svg"))))
    application.setOrganizationName("FileMind")
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)

    if "--smoke-test" in sys.argv:
        image = application.windowIcon().pixmap(64, 64).toImage()
        if image.isNull() or image.pixelColor(32, 32).alpha() == 0:
            raise RuntimeError("Bundled FileMind icon did not render")

    window = MainWindow()
    window.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(1500, window.close)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
