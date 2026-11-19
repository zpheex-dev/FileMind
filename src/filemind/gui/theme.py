"""Shared instrument-panel palette and desktop controls."""

from PySide6.QtGui import QFontDatabase

WINDOW = "#070d15"
PANEL = "#0c1622"
GRID = "#263a4b"
CYAN = "#55d6f0"
AMBER = "#ffaa4c"
SUCCESS = "#57d8a0"
ERROR = "#f47b81"


def fixed_font():
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


APP_STYLESHEET = """
QWidget { color: #e7eff6; font-size: 10pt; }
QMainWindow, QWidget#AppRoot, QWidget#ContentArea, QWidget#PageContainer, QScrollArea { background: #070d15; }
QFrame#Header, QFrame#Sidebar, QDialog, QMenu, QComboBox QAbstractItemView { background: #0c1622; }
QFrame#Sidebar { border-right: 1px solid #263a4b; }
QFrame#Header { border-bottom: 1px solid #314958; }
QFrame#SurfaceCard { background: #0c1622; border: 1px solid #263a4b; }
QLabel { background: transparent; }
QLabel#BrandName { font-size: 18pt; font-weight: 700; letter-spacing: -1px; }
QLabel#WelcomeTitle { font-size: 24pt; font-weight: 650; }
QLabel#HeroTitle { font-size: 34pt; font-weight: 700; letter-spacing: -2px; }
QLabel#HeaderTitle, QLabel#EmptyTitle { font-size: 13pt; font-weight: 600; }
QLabel#CardTitle { font-weight: 650; font-size: 13pt; }
QLabel#MetricLabel, QLabel#SectionCaption { color: #83c5d2; font-size: 9pt; }
QLabel#MetricValue { font-size: 23pt; font-weight: 600; }
QLabel#MutedText, QLabel#HeaderSubtitle, QLabel#EmptyDescription { color: #a8baca; }
QLabel#StatusBadge, QLabel#StatusBadgeMuted { color: #7ce0bb; background: #10262b; padding: 5px 8px; }
QLabel#StatusBadgeMuted { color: #ffd19c; background: #34271d; }
QPushButton { background: #132434; border: 1px solid #3b5365; padding: 7px 12px; }
QPushButton:hover, QMenu::item:selected { background: #203c4c; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QTableView:focus, QPlainTextEdit:focus { border: 1px solid #55d6f0; }
QPushButton#NavButton { border: 1px solid transparent; text-align: left; padding: 10px 8px; background: transparent; }
QPushButton#NavButton:hover { background: #132434; }
QPushButton#NavButton:checked { background: #102c39; color: #8ce6f8; border-left: 3px solid #55d6f0; }
QPushButton#NavButton:focus { border: 1px solid #55d6f0; }
QPushButton#PrimaryButton { background: #55d6f0; color: #07131a; font-weight: 650; }
QPushButton#ReviewButton, QMessageBox QPushButton[text="&Yes"], QMessageBox QPushButton[text="Yes"] { background: #ffaa4c; color: #1c130a; font-weight: 650; }
QPushButton#PrimaryButton:hover { background: #96ecfa; }
QPushButton#ReviewButton:hover { background: #ffc387; }
QPushButton:disabled, QPushButton#PrimaryButton:disabled, QPushButton#ReviewButton:disabled { color: #8c9ca9; background: #19242e; border-color: #27343e; }
QLineEdit, QComboBox, QPlainTextEdit, QTableView, QTreeView { background: #0a1420; border: 1px solid #2a4051; selection-background-color: #174252; selection-color: white; }
QLineEdit, QComboBox, QPlainTextEdit { padding: 6px; }
QTableView, QTreeView { alternate-background-color: #0d1b28; gridline-color: #213343; }
QTableView::item:focus { border: 1px solid #55d6f0; }
QHeaderView::section, QTableCornerButton::section { background: #152635; color: #c6d7e1; border: 0; border-bottom: 1px solid #355061; padding: 7px; text-align: left; }
QScrollArea { border: 0; }
QScrollBar:vertical { width: 10px; background: #0c1622; }
QScrollBar:horizontal { height: 10px; background: #0c1622; }
QScrollBar::handle { background: #456073; min-height: 20px; min-width: 20px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QSplitter::handle { background: #263a4b; }
QStatusBar { background: #0c1622; border-top: 1px solid #263a4b; color: #a9bdc9; }
QProgressBar { border: 0; background: #193140; }
QProgressBar::chunk { background: #55d6f0; }
QToolTip { color: #e7eff6; background: #112434; border: 1px solid #557485; padding: 5px; }
"""
