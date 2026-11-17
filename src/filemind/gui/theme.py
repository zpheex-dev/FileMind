"""Compact graphite and cyan theme rendered by Qt on both platforms."""

APP_STYLESHEET = """
QWidget { color: #ccd5df; font-size: 9pt; }
QMainWindow, QWidget#AppRoot, QWidget#ContentArea, QWidget#PageContainer { background: #0b0e13; }
QFrame#Sidebar { background: #10141b; border-right: 1px solid #242c37; }
QFrame#Header { background: #0e1218; border-bottom: 1px solid #242c37; }
QLabel { background: transparent; }
QLabel#BrandMark { background: #122e30; border: 1px solid #387f7b; border-radius: 6px; color: #66f1db; font-size: 17pt; font-weight: 700; }
QLabel#BrandName { color: #eff5fc; font-size: 16pt; font-weight: 700; }
QLabel#BrandCaption, QLabel#SectionCaption { color: #708292; font-size: 7pt; letter-spacing: 1px; }
QLabel#MutedText, QLabel#HeaderSubtitle { color: #8b9baa; font-size: 9pt; }
QLabel#HeaderTitle { color: #edf4fc; font-size: 16pt; font-weight: 600; }
QLabel#WelcomeTitle { color: #edf4fc; font-size: 22pt; font-weight: 600; }
QPushButton { padding: 7px 12px; border-radius: 4px; }
QPushButton#NavButton { background: transparent; border: 1px solid transparent; color: #94a5b6; padding: 9px 10px; text-align: left; }
QPushButton#NavButton:hover { color: #e8f1f9; background: #1a232e; }
QPushButton#NavButton:checked { color: #63e8d7; background: #142b2e; border: 1px solid #244d50; border-left: 3px solid #53dfcd; }
QPushButton#PrimaryButton { color: #071713; background: #53dfcd; border: 1px solid #6cebdc; font-weight: 700; }
QPushButton#PrimaryButton:hover { background: #83f5e5; }
QPushButton#SecondaryButton { color: #b7c6d6; background: #1a2430; border: 1px solid #344456; }
QPushButton:disabled, QPushButton#PrimaryButton:disabled { color: #687784; background: #1c2630; border: 1px solid #2c3945; }
QFrame#SurfaceCard, QFrame#WelcomeCard { background: #121820; border: 1px solid #29323f; border-radius: 6px; }
QFrame#WelcomeCard { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #142c30,stop:1 #121820); border: 1px solid #315454; }
QLabel#CardTitle { color: #e3edf7; font-size: 10pt; font-weight: 600; }
QLabel#MetricLabel { color: #91a4b6; font-size: 8pt; letter-spacing: 1px; }
QLabel#MetricValue { color: #70e8d8; font-size: 26pt; font-weight: 600; }
QLabel#StatusBadge, QLabel#StatusBadgeMuted { color: #64e4d1; background: #112a29; border: 1px solid #2a5550; border-radius: 3px; font-size: 7pt; font-weight: 600; padding: 5px 8px; }
QLabel#StatusBadgeMuted { color: #e2bd76; background: #29241a; border-color: #51462f; }
QLabel#EmptyIcon { color: #3e857f; font-size: 22pt; }
QLabel#EmptyTitle { color: #c2d2df; font-size: 11pt; font-weight: 600; }
QLabel#EmptyDescription { color: #8b9baa; }
QLineEdit, QComboBox, QPlainTextEdit { color: #d1deeb; background: #0c1118; border: 1px solid #2c3948; border-radius: 4px; padding: 7px 9px; selection-background-color: #24515a; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #4fb6ad; }
QLineEdit:disabled, QComboBox:disabled { color: #61707e; }
QComboBox QAbstractItemView { background: #151e28; selection-background-color: #24515a; }
QPlainTextEdit#ContentPreview { font-family: "Cascadia Mono", "DejaVu Sans Mono", monospace; font-size: 9pt; }
QTableView, QTableWidget, QTreeWidget { color: #bfcedc; background: #0f151d; alternate-background-color: #131b25; border: 1px solid #293543; border-radius: 4px; gridline-color: #202c38; selection-background-color: #1c4149; selection-color: #efffff; outline: 0; }
QTableView::item { padding: 3px 7px; border: none; }
QTreeWidget::item { padding: 4px 6px; }
QHeaderView::section { color: #8fa6ba; background: #19222d; border: none; border-bottom: 1px solid #344455; padding: 8px 7px; font-size: 8pt; font-weight: 600; }
QTableCornerButton::section { background: #19222d; border: none; }
QProgressBar { background: #24313e; border: none; border-radius: 2px; }
QProgressBar::chunk { background: #53dfcd; }
QScrollArea { background: #0b0e13; border: none; }
QStackedWidget { background: transparent; }
QSplitter::handle { background: #27343f; width: 2px; margin: 6px; }
QStatusBar { color: #7c97a9; background: #101720; border-top: 1px solid #293543; font-size: 8pt; }
QStatusBar::item { border: none; }
QScrollBar:vertical { background: #0e141c; width: 8px; margin: 0; }
QScrollBar:horizontal { background: #0e141c; height: 8px; margin: 0; }
QScrollBar::handle { background: #364b5b; border-radius: 3px; min-height: 24px; min-width: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QToolTip { background: #1a2834; color: #dbf2f5; border: 1px solid #385564; padding: 6px; }
QMessageBox { background: #121820; }
"""
