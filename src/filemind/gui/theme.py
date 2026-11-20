"""Shared forest-charcoal palette for the desktop workspace."""

from PySide6.QtGui import QColor, QFontDatabase, QPalette

WINDOW = "#0e1512"
PANEL = "#151e19"
BORDER = "#33483b"
TEXT = "#dbe8dd"
MUTED = "#a8bbad"
ACTIVE = "#a5e6b7"
SELECTION = "#294334"
AMBER = "#e1bf82"
SUCCESS = ACTIVE


def fixed_font():
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)


def workspace_palette():
    palette = QPalette()
    role = QPalette.ColorRole
    for key, color in (
        (role.Window, PANEL), (role.WindowText, TEXT), (role.Base, WINDOW),
        (role.Text, TEXT), (role.Button, PANEL), (role.ButtonText, TEXT),
        (role.Highlight, ACTIVE), (role.HighlightedText, WINDOW),
        (role.PlaceholderText, MUTED), (role.ToolTipBase, PANEL), (role.ToolTipText, TEXT),
    ):
        palette.setColor(key, QColor(color))
    return palette


APP_STYLESHEET = f"""
QWidget {{ color: {TEXT}; font-size: 10pt; }}
QMainWindow, QWidget#AppRoot, QWidget#ContentArea, QWidget#PageContainer, QScrollArea {{
    background: {WINDOW};
}}
QFrame#Header, QFrame#Sidebar, QDialog, QMenu, QComboBox QAbstractItemView {{ background: {PANEL}; }}
QFrame#Sidebar {{ border-right: 1px solid {BORDER}; }}
QFrame#Header {{ border-bottom: 1px solid {BORDER}; }}
QFrame#SurfaceCard {{ background: {PANEL}; border: 1px solid {BORDER}; }}
QLabel {{ background: transparent; }}
QLabel#BrandName {{ color: {ACTIVE}; font-size: 14pt; font-weight: bold; }}
QLabel#HeaderTitle {{ font-size: 17pt; font-weight: bold; }}
QLabel#CardTitle, QLabel#EmptyTitle {{ font-size: 11pt; font-weight: bold; }}
QLabel#SectionCaption {{ color: {ACTIVE}; font-weight: bold; }}
QLabel#MutedText, QLabel#HeaderSubtitle, QLabel#EmptyDescription {{ color: {MUTED}; }}
QLabel#StatusBadge, QLabel#StatusBadgeMuted {{ color: {ACTIVE}; padding: 4px 8px; }}
QLabel#StatusBadgeMuted {{ color: {AMBER}; }}

QPushButton {{ background: {PANEL}; border: 1px solid #496354; padding: 6px 10px; }}
QPushButton:hover, QMenu::item:selected {{ background: #213428; }}
QPushButton:pressed, QPushButton:checked {{ background: {SELECTION}; }}
QPushButton#NavButton {{ border: 1px solid transparent; text-align: left; background: transparent; }}
QPushButton#NavButton:hover {{ background: #213428; }}
QPushButton#NavButton:checked {{
    background: {SELECTION}; color: {ACTIVE}; border-left: 3px solid {ACTIVE}; font-weight: bold;
}}
QPushButton#PrimaryButton, QPushButton#ReviewButton {{
    background: {ACTIVE}; color: {WINDOW}; font-weight: bold;
}}
QPushButton#PrimaryButton:hover, QPushButton#ReviewButton:hover {{ background: #c2f0cc; }}
QPushButton:disabled, QPushButton#PrimaryButton:disabled, QPushButton#ReviewButton:disabled {{
    color: #8a9b8f; background: {PANEL}; border-color: {BORDER};
}}
QPushButton:focus, QPushButton#NavButton:focus, QLineEdit:focus, QComboBox:focus,
QAbstractItemView:focus, QPlainTextEdit:focus {{ border: 1px solid {ACTIVE}; }}
QPushButton#PrimaryButton:focus, QPushButton#ReviewButton:focus {{ border: 1px dashed {WINDOW}; }}

QLineEdit, QComboBox, QPlainTextEdit, QTableView, QTreeView {{
    background: {WINDOW}; border: 1px solid {BORDER};
    selection-background-color: {SELECTION}; selection-color: {TEXT};
}}
QLineEdit, QComboBox, QPlainTextEdit {{ padding: 5px; }}
QTableView, QTreeView {{ alternate-background-color: #111b15; gridline-color: {BORDER}; }}
QTableView::item:focus, QTreeView::item:focus {{ border: 1px solid {ACTIVE}; }}
QHeaderView::section, QTableCornerButton::section {{
    background: #1b2920; color: {TEXT}; border: 0; border-bottom: 1px solid {BORDER};
    padding: 6px; text-align: left;
}}
QScrollArea {{ border: 0; }}
QScrollBar:vertical {{ width: 11px; background: {PANEL}; }}
QScrollBar:horizontal {{ height: 11px; background: {PANEL}; }}
QScrollBar::handle {{ background: #486454; min-height: 20px; min-width: 20px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QSplitter::handle {{ background: {BORDER}; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QProgressBar {{ border: 0; background: {SELECTION}; }}
QProgressBar::chunk {{ background: {ACTIVE}; }}
QToolTip {{ color: {TEXT}; background: {PANEL}; border: 1px solid #496354; padding: 5px; }}
"""
