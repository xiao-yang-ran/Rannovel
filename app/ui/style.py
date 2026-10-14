"""A quiet, literary blue-ink palette for the offline writing desk."""

APP_STYLE = """
QWidget {
    background-color: #F6F1E8;
    color: #332F2A;
    font-family: "Microsoft YaHei UI";
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #F6F1E8; }
QWidget#contentSurface { background-color: #F6F1E8; }
QFrame#sidebar {
    background-color: #294457;
    border: none;
    border-right: 1px solid #3C5868;
}
QFrame#sidebarBrand, QFrame#sidebarFooter {
    background: transparent;
    border: none;
}
QLabel#seal {
    background: #AF624B;
    color: #FFF8E8;
    border: 1px solid #C68565;
    border-radius: 11px;
    font-family: "KaiTi";
    font-size: 26px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}
QLabel#brand {
    background: transparent;
    color: #FBF0DA;
    font-family: "Georgia";
    font-size: 25px;
    font-weight: bold;
}
QLabel#subtitle, QLabel#navSection, QLabel#sidebarQuote, QLabel#localNotice {
    background: transparent;
    color: #B5C8D0;
}
QLabel#subtitle { font-size: 11px; }
QLabel#navSection {
    color: #CCA98C;
    font-size: 11px;
    letter-spacing: 2px;
}
QLabel#sidebarQuote {
    color: #E1E4DF;
    font-family: "KaiTi";
    font-size: 15px;
}
QLabel#localNotice { font-size: 11px; }
QListWidget#navigation {
    background: transparent;
    color: #E7ECEB;
    border: none;
    outline: none;
    padding: 0 9px;
}
QListWidget#navigation::item {
    background: transparent;
    border-radius: 10px;
    margin: 3px 0;
    padding: 9px 12px;
    color: #E3EBEA;
}
QListWidget#navigation::item:hover { background: #38586A; }
QListWidget#navigation::item:selected {
    background: #527387;
    color: #FFF8E8;
    border-left: 3px solid #D6A174;
}
QListWidget#inspirationPool, QListWidget#usedInspirationList {
    background: #FFFCF6;
    border: 1px solid #E4DACA;
    border-radius: 11px;
    outline: none;
    font-family: "Microsoft YaHei UI";
    font-size: 15px;
}
QListWidget#inspirationPool::item, QListWidget#usedInspirationList::item {
    padding: 8px 10px;
    border-bottom: 1px solid #F0E9DF;
}
QListWidget#inspirationPool::item:hover, QListWidget#usedInspirationList::item:hover {
    background: #F3ECE1;
}
QListWidget#inspirationPool::item:selected, QListWidget#usedInspirationList::item:selected {
    background: #E5D9C8;
    color: #332F2A;
}
QWidget#heroPanel {
    background: transparent;
    border-radius: 18px;
}
QLabel#heroEyebrow, QLabel#heroTitle, QLabel#heroSubline, QLabel#heroBadge {
    background: transparent;
}
QLabel#heroEyebrow {
    color: #DCC9A9;
    font-family: "Georgia";
    font-size: 10px;
    letter-spacing: 2px;
}
QLabel#heroTitle {
    color: #FFF8E9;
    font-family: "KaiTi";
    font-size: 25px;
    font-weight: bold;
}
QLabel#heroSubline {
    color: #DCE7E9;
    font-size: 12px;
}
QLabel#heroBadge {
    color: #F1DFBC;
    font-size: 11px;
}
QLabel#pageTitle {
    color: #344F62;
    font-family: "KaiTi";
    font-size: 28px;
    font-weight: bold;
    padding-top: 5px;
}
QLabel#pageHint {
    color: #82786C;
    font-size: 12px;
    padding-bottom: 8px;
}
QGroupBox {
    background: #FFFCF6;
    border: 1px solid #E6DBCA;
    border-radius: 13px;
    margin-top: 15px;
    padding: 15px 11px 10px 11px;
    font-weight: normal;
}
QGroupBox#inspirationCard {
    margin-top: 0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    color: #466477;
    font-family: "KaiTi";
    font-size: 17px;
    padding: 0 7px;
}
QGroupBox QLabel {
    background: transparent;
}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {
    background: #FFFEFB;
    border: 1px solid #DFD4C4;
    border-radius: 8px;
    padding: 8px 10px;
    color: #3A352F;
    selection-background-color: #6B91A0;
    selection-color: white;
}
QPlainTextEdit, QTextEdit {
    line-height: 1.5;
}
QPlainTextEdit#inspirationComposer {
    font-family: "KaiTi";
    font-size: 17px;
    line-height: 1.7;
}
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QSpinBox:hover, QComboBox:hover {
    border-color: #CDB89D;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #64879A;
    background: #FFFFFF;
}
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {
    color: #A7A099;
    background: #EEE9E1;
}
QComboBox::drop-down { border: none; width: 25px; }
QComboBox QAbstractItemView {
    background: #FFFCF6;
    border: 1px solid #DFD4C4;
    selection-background-color: #E7D9C5;
    selection-color: #332F2A;
}
QPushButton {
    background: #EDE5D8;
    color: #4B473F;
    border: 1px solid #DED1BE;
    border-radius: 9px;
    padding: 8px 15px;
    min-height: 22px;
    font-weight: 500;
}
QPushButton:hover {
    background: #E2D6C5;
    border-color: #CAB69D;
}
QPushButton:pressed { background: #D9C8B4; }
QPushButton:disabled {
    background: #F1EDE7;
    color: #A9A198;
    border-color: #E6E1DA;
}
QPushButton#compactButton {
    min-width: 22px;
    padding: 8px 7px;
    font-family: "Georgia";
    font-weight: bold;
}
QPushButton#primaryButton {
    background: #547D91;
    color: #FFF8EB;
    border: 1px solid #476B7D;
    font-weight: bold;
}
QPushButton#primaryButton:hover { background: #648FA3; }
QPushButton#primaryButton:pressed { background: #416678; }
QPushButton#dangerButton {
    color: #9C554B;
    background: #F6EBE5;
    border-color: #E9D5CD;
}
QPushButton#dangerButton:hover { background: #EFDCD5; }
QTableWidget, QTreeWidget, QListWidget#tagPicker {
    background: #FFFCF6;
    alternate-background-color: #F9F4EC;
    border: 1px solid #E4DACA;
    border-radius: 11px;
    gridline-color: #EEE6DA;
    outline: none;
    selection-background-color: #E9DCCB;
    selection-color: #332F2A;
}
QTableWidget::item, QTreeWidget::item {
    padding: 8px 6px;
}
QTableWidget::item:selected, QTreeWidget::item:selected {
    background: #E9DCCB;
    color: #332F2A;
}
QHeaderView::section {
    background: #EFE6D8;
    color: #526774;
    border: none;
    border-right: 1px solid #E2D5C4;
    border-bottom: 1px solid #E2D5C4;
    padding: 9px 8px;
    font-weight: bold;
    font-size: 12px;
}
QTabWidget::pane {
    border: 1px solid #E3D9CA;
    border-radius: 11px;
    background: #FFFCF6;
    top: -1px;
}
QTabBar::tab {
    background: #EEE8DD;
    color: #776D61;
    border: 1px solid #E3D9CA;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 9px 21px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #FFFCF6;
    color: #4C7186;
    font-weight: bold;
}
QTabBar::tab:hover:!selected { background: #E7DECF; }
QCheckBox {
    spacing: 7px;
    color: #466477;
}
QWidget#geographyPage QLabel#pageHint { font-size: 13px; }
QTableWidget#geographyTable {
    font-family: "Microsoft YaHei UI";
    font-size: 15px;
}
QHeaderView#geographyHeader {
    font-size: 14px;
}
QHeaderView#geographyHeader::section {
    font-size: 14px;
    padding: 11px 8px;
}
QDialog#geographyDialog QLabel,
QDialog#geographyDialog QLineEdit,
QDialog#geographyDialog QComboBox,
QDialog#geographyDialog QPlainTextEdit {
    font-size: 14px;
}
QLabel#emptyHint {
    background: transparent;
    color: #8C8375;
    font-family: "KaiTi";
    font-size: 18px;
}
QSplitter::handle { background: transparent; }
QScrollArea {
    background: #F6F1E8;
    border: none;
}
QScrollBar:vertical {
    background: #F2ECE3;
    width: 10px;
    margin: 2px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #C7B9A5;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}
QMenuBar {
    background: #F2EADF;
    color: #5D574F;
    border-bottom: 1px solid #E5DACB;
    padding: 4px;
}
QMenuBar::item:selected { background: #E8D8C5; border-radius: 5px; }
QMenu {
    background: #FFFCF6;
    border: 1px solid #E1D5C5;
    padding: 5px;
}
QMenu::item { padding: 6px 24px; }
QMenu::item:selected { background: #E8D8C5; color: #332F2A; }
QStatusBar {
    background: #F2EADF;
    color: #7A746B;
    border-top: 1px solid #E4D8C9;
    font-size: 11px;
}
QDialogButtonBox QPushButton { min-width: 75px; }
QToolTip {
    background: #344F62;
    color: #FFF8E9;
    border: 1px solid #6D8997;
    padding: 5px 8px;
}
"""
