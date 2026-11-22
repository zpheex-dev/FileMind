"""Shared forest-charcoal palette for the desktop workspace."""

from PySide6.QtGui import QColor, QFontDatabase, QPalette

WINDOW = "#070e0c"
PANEL = "#0c1713"
BORDER = "#34534a"
TEXT = "#edf4f0"
MUTED = "#b4c7bf"
ACTIVE = "#9af0cf"
SELECTION = "#13382c"
TRACK = "#1b382e"
AMBER = "#f1c989"
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
QMainWindow, QWidget#AppRoot, QWidget#ContentArea, QWidget#PageContainer, QStackedWidget#WorkspacePages, QScrollArea {{
    background: {WINDOW};
}}
QFrame#Header, QFrame#Sidebar, QDialog, QMenu, QComboBox QAbstractItemView {{ background: {PANEL}; }}
QFrame#Header {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #0a1411, stop: 1 {WINDOW});
    border-bottom: 1px solid #273e36;
}}
QFrame#Sidebar {{ background: #0a1411; border-right: 1px solid #273e36; }}
QFrame#SurfaceCard, QFrame#GraphsCard {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #0c1713, stop: 1 #0a1410);
    border: 1px solid {BORDER}; border-radius: 11px;
}}
QFrame#CardDivider {{ background: {BORDER}; border: 0; }}
QLabel {{ background: transparent; }}
QLabel#BrandName {{ color: {ACTIVE}; font-size: 14pt; font-weight: bold; }}
QLabel#HeaderTitle {{ font-size: 20pt; font-weight: bold; }}
QLabel#CardTitle, QLabel#EmptyTitle {{ font-size: 12pt; font-weight: bold; }}
QLabel#GraphTitle, QLabel#ScanMetric {{ font-size: 15pt; font-weight: bold; }}
QLabel#ChartInsight {{ font-size: 16pt; font-weight: bold; }}
QLabel#ScanTiming {{ font-size: 9pt; }}
QLabel#ScanError {{ color: {AMBER}; }}
QLabel#SectionCaption {{ color: {ACTIVE}; font-size: 9pt; font-weight: bold; }}
QLabel#MutedText, QLabel#HeaderSubtitle, QLabel#EmptyDescription {{ color: {MUTED}; }}
QLabel#StatusBadge, QLabel#StatusBadgeMuted {{
    color: {ACTIVE}; background: #1b332b; border: 1px solid #345549; border-radius: 11px;
    padding: 4px 11px; font-size: 8pt; font-weight: bold;
}}
QLabel#StatusBadgeMuted {{ color: {AMBER}; background: #332b20; border-color: #594832; }}
QLabel#StatusBadge[scanSummary="true"], QLabel#StatusBadgeMuted[scanSummary="true"] {{
    font-size: 10pt; padding: 4px 9px; border-radius: 11px;
}}
QLabel#StatusBadge[scanSummary="true"] {{ border-color: {ACTIVE}; }}

QPushButton {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #14251e, stop: 1 #0e1d17);
    border: 1px solid #334d43; border-radius: 8px; padding: 6px 11px;
}}
QPushButton:hover, QMenu::item:selected {{ background: #294339; }}
QPushButton:pressed, QPushButton:checked {{ background: {SELECTION}; }}
QPushButton#NavButton {{
    border: 1px solid transparent; text-align: left; background: transparent; color: {TEXT};
    padding: 8px 10px;
}}
QPushButton#NavButton:hover {{ background: #223631; color: {TEXT}; }}
QPushButton#NavButton:checked {{
    background: {SELECTION}; color: {ACTIVE}; border-color: {ACTIVE}; font-weight: bold;
}}
QPushButton#PrimaryButton, QPushButton#ReviewButton {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #bdf6dc, stop: 1 #83deb6);
    color: #10271f; border-color: #a7f0cf; font-weight: bold;
}}
QPushButton#PrimaryButton:hover, QPushButton#ReviewButton:hover {{ background: #c7f9e3; }}
QPushButton#PrimaryButton:pressed, QPushButton#ReviewButton:pressed {{ background: #82d5af; }}
QPushButton:disabled, QPushButton#PrimaryButton:disabled, QPushButton#ReviewButton:disabled {{
    color: #8ba49b; background: {PANEL}; border-color: {BORDER};
}}
QPushButton:focus, QPushButton#NavButton:focus, QLineEdit:focus, QComboBox:focus,
QAbstractItemView:focus, QPlainTextEdit:focus {{ border: 1px solid {ACTIVE}; }}
QPushButton#PrimaryButton:focus, QPushButton#ReviewButton:focus {{ border: 1px dashed {WINDOW}; }}
QWidget#ChartSegments {{
    background: #0c1914; border: 1px solid #2e4c40; border-radius: 8px;
}}
QPushButton#ChartSegment {{
    background: transparent; border: 1px solid transparent; border-radius: 7px;
    padding: 3px 15px;
}}
QPushButton#ChartSegment:hover {{ background: #1b382e; }}
QPushButton#ChartSegment:checked {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #bdfbe4, stop: 1 #83e2be);
    color: #0a1d15; font-weight: bold;
}}
QPushButton#ChartSegment:focus {{ border-color: {ACTIVE}; }}
QPushButton#ChartSegment:checked:focus {{ border-color: #23493d; }}

QLineEdit, QComboBox, QPlainTextEdit, QTableView, QTreeView {{
    background: #0a1410; border: 1px solid {BORDER}; border-radius: 8px;
    selection-background-color: {SELECTION}; selection-color: {TEXT};
}}
QLineEdit, QComboBox, QPlainTextEdit {{ padding: 6px 8px; }}
QTableView, QTreeView {{ alternate-background-color: #0f1c16; gridline-color: {BORDER}; }}
QTableView::item:hover:!selected, QTreeView::item:hover:!selected {{ background: #203630; }}
QTableView::item:focus, QTreeView::item:focus {{ border: 1px solid {ACTIVE}; }}
QTreeView#InventoryTree::item {{ height: 24px; }}
QTreeView#ChartLegend {{ background: transparent; border: 0; }}
QTreeView#ChartLegend::item {{ background: transparent; border: 0; }}
QHeaderView::section, QTableCornerButton::section {{
    background: #13251d; color: {MUTED}; border: 0; border-bottom: 1px solid {BORDER};
    padding: 7px 8px; text-align: left; font-weight: bold;
}}
QScrollArea {{ border: 0; }}
QScrollBar:vertical {{ width: 10px; background: {PANEL}; }}
QScrollBar:horizontal {{ height: 10px; background: {PANEL}; }}
QScrollBar::handle {{
    background: #45665b; min-height: 26px; min-width: 26px; border-radius: 5px; border: 1px solid {PANEL};
}}
QScrollBar::handle:hover {{ background: #638c7e; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {TRACK}; border-radius: 2px; }}
QSplitter::handle:hover {{ background: #5a8b79; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QStatusBar::item {{ border: 0; }}
QToolTip {{ color: {TEXT}; background: #21322d; border: 1px solid #49695e; padding: 5px; }}
"""
