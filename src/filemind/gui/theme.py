"""Shared visual theme for the FileMind desktop interface."""

APP_STYLESHEET = """
QWidget {
    color: #E7EDF7;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QWidget#AppRoot, QWidget#ContentArea {
    background-color: #0B1220;
}
QFrame#Sidebar {
    background-color: #0D1728;
    border-right: 1px solid #1B2940;
}
QFrame#Header {
    background-color: #0B1220;
    border-bottom: 1px solid #1B2940;
}
QLabel#BrandMark {
    background-color: #6C8CFF;
    border-radius: 11px;
    color: #FFFFFF;
    font-size: 15pt;
    font-weight: 700;
}
QLabel#BrandName {
    color: #F4F7FC;
    font-size: 15pt;
    font-weight: 700;
}
QLabel#BrandCaption, QLabel#SectionCaption, QLabel#MutedText {
    color: #8492A9;
}
QLabel#BrandCaption {
    font-size: 8pt;
    letter-spacing: 1px;
}
QLabel#SectionCaption {
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#HeaderTitle {
    color: #F4F7FC;
    font-size: 17pt;
    font-weight: 650;
}
QLabel#HeaderSubtitle {
    color: #8492A9;
    font-size: 9pt;
}
QLabel#WelcomeTitle {
    color: #F4F7FC;
    font-size: 16pt;
    font-weight: 700;
}
QPushButton#NavButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    color: #A8B4C7;
    font-size: 10pt;
    font-weight: 550;
    padding: 10px 12px;
    text-align: left;
}
QPushButton#NavButton:hover {
    background-color: #142139;
    color: #E7EDF7;
}
QPushButton#NavButton:checked {
    background-color: #1A2A47;
    border-color: #263D64;
    color: #FFFFFF;
}
QPushButton#PrimaryButton {
    background-color: #6C8CFF;
    border: 1px solid #6C8CFF;
    border-radius: 8px;
    color: #FFFFFF;
    font-weight: 650;
    padding: 9px 15px;
}
QPushButton#PrimaryButton:hover {
    background-color: #7D99FF;
}
QPushButton#PrimaryButton:disabled {
    background-color: #26334B;
    border-color: #26334B;
    color: #78869E;
}
QPushButton#SecondaryButton {
    background-color: #17243A;
    border: 1px solid #2A3B58;
    border-radius: 8px;
    color: #DCE5F3;
    font-weight: 600;
    padding: 9px 15px;
}
QPushButton#SecondaryButton:hover {
    background-color: #1D2D48;
    border-color: #3A5277;
}
QPushButton#SecondaryButton:disabled {
    color: #78869E;
}
QFrame#SurfaceCard, QFrame#WelcomeCard {
    background-color: #111C2E;
    border: 1px solid #21314B;
    border-radius: 12px;
}
QFrame#WelcomeCard {
    background-color: #14213A;
    border-color: #293E64;
}
QLabel#CardTitle {
    color: #E7EDF7;
    font-size: 11pt;
    font-weight: 650;
}
QLabel#PageTitle {
    color: #F4F7FC;
    font-size: 20pt;
    font-weight: 700;
}
QLabel#PageDescription {
    color: #91A0B6;
}
QLabel#MetricValue {
    color: #F4F7FC;
    font-size: 23pt;
    font-weight: 700;
}
QLabel#MetricLabel {
    color: #AAB7CA;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#StatusBadge {
    background-color: #122B2B;
    border: 1px solid #24504C;
    border-radius: 10px;
    color: #86D6C1;
    font-size: 8pt;
    font-weight: 700;
    padding: 5px 10px;
}
QLabel#StatusBadgeMuted {
    background-color: #19253A;
    border: 1px solid #2A3B58;
    border-radius: 10px;
    color: #AAB7CA;
    font-size: 8pt;
    font-weight: 700;
    padding: 5px 10px;
}
QLabel#EmptyIcon {
    color: #7185A8;
    font-size: 25pt;
}
QLabel#EmptyTitle {
    color: #DCE5F3;
    font-size: 11pt;
    font-weight: 650;
}
QLabel#EmptyDescription {
    color: #8492A9;
}
QLineEdit, QComboBox {
    background-color: #0D1728;
    border: 1px solid #263650;
    border-radius: 7px;
    color: #DCE5F3;
    padding: 8px 10px;
    selection-background-color: #405D9C;
}
QPlainTextEdit {
    background-color: #0D1728;
    border: 1px solid #263650;
    border-radius: 8px;
    color: #DCE5F3;
    padding: 10px;
    selection-background-color: #405D9C;
}
QProgressBar#ScanProgress {
    background-color: #19253A;
    border: none;
    border-radius: 3px;
}
QProgressBar#ScanProgress::chunk {
    background-color: #6C8CFF;
    border-radius: 3px;
}
QLineEdit:disabled, QComboBox:disabled {
    color: #718096;
    background-color: #101A2B;
}
QTableWidget, QTreeWidget {
    background-color: #0F192A;
    alternate-background-color: #111D30;
    border: 1px solid #21314B;
    border-radius: 8px;
    gridline-color: #1C2A40;
    selection-background-color: #263C63;
    outline: 0;
}
QTreeWidget::item {
    padding: 5px 3px;
}
QHeaderView::section {
    background-color: #142139;
    border: none;
    border-bottom: 1px solid #263650;
    color: #91A0B6;
    font-size: 8pt;
    font-weight: 700;
    padding: 10px 8px;
}
QScrollArea {
    background-color: #0B1220;
    border: none;
}
QWidget#PageContainer, QStackedWidget {
    background-color: #0B1220;
}
QStackedWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    margin: 2px;
    width: 9px;
}
QScrollBar::handle:vertical {
    background: #2A3B58;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
}
"""
