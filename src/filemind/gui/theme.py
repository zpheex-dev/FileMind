"""Monochrome desktop workspace."""

APP_STYLESHEET = """
QWidget { color: #d4d4d4; font-size: 9pt; }
QMainWindow, QWidget#AppRoot, QWidget#ContentArea, QWidget#PageContainer { background: #0e0e0e; }
QFrame#Sidebar { background: #141414; border-right: 1px solid #2b2b2b; }
QFrame#Header { background: #121212; border-bottom: 1px solid #2b2b2b; }
QLabel { background: transparent; }
QLabel#BrandMark { background: #282828; border: 1px solid #707070; border-radius: 6px; color: #d2d2d2; font-size: 17pt; font-weight: 700; }
QLabel#BrandName { color: #f4f4f4; font-size: 16pt; font-weight: 700; }
QLabel#BrandCaption, QLabel#SectionCaption { color: #7f7f7f; font-size: 7pt; letter-spacing: 1px; }
QLabel#MutedText, QLabel#HeaderSubtitle { color: #999999; font-size: 9pt; }
QLabel#HeaderTitle { color: #f3f3f3; font-size: 16pt; font-weight: 600; }
QLabel#WelcomeTitle { color: #f3f3f3; font-size: 22pt; font-weight: 600; }
QPushButton { padding: 7px 12px; border-radius: 4px; }
QPushButton#NavButton { background: transparent; border: 1px solid transparent; color: #a3a3a3; padding: 9px 10px; text-align: left; }
QPushButton#NavButton:hover { color: #f0f0f0; background: #222222; }
QPushButton#NavButton:checked { color: #cbcbcb; background: #262626; border: 1px solid #454545; border-left: 3px solid #c0c0c0; }
QPushButton#PrimaryButton { color: #131313; background: #c0c0c0; border: 1px solid #cfcfcf; font-weight: 700; }
QPushButton#PrimaryButton:hover { background: #dcdcdc; }
QPushButton#SecondaryButton { color: #c4c4c4; background: #232323; border: 1px solid #424242; }
QPushButton:disabled, QPushButton#PrimaryButton:disabled { color: #757575; background: #252525; border: 1px solid #373737; }
QFrame#SurfaceCard, QFrame#WelcomeCard { background: #171717; border: 1px solid #313131; border-radius: 6px; }
QFrame#WelcomeCard { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #272727,stop:1 #171717); border: 1px solid #4d4d4d; }
QLabel#CardTitle { color: #ececec; font-size: 10pt; font-weight: 600; }
QLabel#MetricLabel { color: #a1a1a1; font-size: 8pt; letter-spacing: 1px; }
QLabel#MetricValue { color: #cecece; font-size: 26pt; font-weight: 600; }
QLabel#StatusBadge, QLabel#StatusBadgeMuted { color: #c8c8c8; background: #252525; border: 1px solid #4c4c4c; border-radius: 3px; font-size: 7pt; font-weight: 600; padding: 5px 8px; }
QLabel#StatusBadgeMuted { color: #c0c0c0; background: #242424; border-color: #474747; }
QLabel#EmptyIcon { color: #767676; font-size: 22pt; }
QLabel#EmptyTitle { color: #d0d0d0; font-size: 11pt; font-weight: 600; }
QLabel#EmptyDescription { color: #999999; }
QLineEdit, QComboBox, QPlainTextEdit { color: #dcdcdc; background: #101010; border: 1px solid #373737; border-radius: 4px; padding: 7px 9px; selection-background-color: #484848; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #a0a0a0; }
QLineEdit:disabled, QComboBox:disabled { color: #6e6e6e; }
QComboBox QAbstractItemView { background: #1d1d1d; selection-background-color: #484848; }
QPlainTextEdit#ContentPreview { font-family: "Cascadia Mono", "DejaVu Sans Mono", monospace; font-size: 9pt; }
QTableView, QTableWidget, QTreeWidget { color: #cccccc; background: #141414; alternate-background-color: #1a1a1a; border: 1px solid #333333; border-radius: 4px; gridline-color: #2a2a2a; selection-background-color: #3a3a3a; selection-color: #fcfcfc; outline: 0; }
QTableView::item { padding: 3px 7px; border: none; }
QTreeWidget::item { padding: 4px 6px; }
QHeaderView::section { color: #a3a3a3; background: #212121; border: none; border-bottom: 1px solid #424242; padding: 8px 7px; font-size: 8pt; font-weight: 600; }
QTableCornerButton::section { background: #212121; border: none; }
QProgressBar { background: #2f2f2f; border: none; border-radius: 2px; }
QProgressBar::chunk { background: #c0c0c0; }
QScrollArea { background: #0e0e0e; border: none; }
QStackedWidget { background: transparent; }
QSplitter::handle { background: #323232; width: 2px; margin: 6px; }
QStatusBar { color: #939393; background: #161616; border-top: 1px solid #333333; font-size: 8pt; }
QStatusBar::item { border: none; }
QScrollBar:vertical { background: #131313; width: 8px; margin: 0; }
QScrollBar:horizontal { background: #131313; height: 8px; margin: 0; }
QScrollBar::handle { background: #484848; border-radius: 3px; min-height: 24px; min-width: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QToolTip { background: #262626; color: #ededed; border: 1px solid #505050; padding: 6px; }
QDialog { background: #181818; }
QPushButton { color: #ededed; background: #222222; border: 1px solid #535353; border-radius: 0px; }
QPushButton:hover { background: #353535; }
QPushButton:focus { border: 1px solid white; }
QPushButton:disabled { color: #888888; background: #171717; }
QPushButton#NavButton { padding: 8px 12px; }
QPushButton#NavButton:checked { background: #282828; color: white; border: none; border-bottom: 2px solid white; }
QPushButton#PrimaryButton { background: #f1f1f1; color: #101010; border: 1px solid white; border-radius: 0px; }
QPushButton#PrimaryButton:hover { background: #cccccc; }
QPushButton#MapNode { font-family: monospace; background: #181818; padding: 5px 10px; border-color: #888888; }
QPushButton#MapNode:hover, QPushButton#MapNode:focus { color: black; background: white; }
QFrame#SurfaceCard { background: #141414; border: 1px solid #353535; border-radius: 0px; }
QFrame#Sidebar { background: #080808; border: none; border-bottom: 1px solid #353535; }
QLabel#MetricValue { color: #ffffff; font-size: 22pt; }
QLabel#MetricLabel, QLabel#StatusBadge, QLabel#StatusBadgeMuted { font-family: monospace; }
QMessageBox { background: #171717; }
"""
