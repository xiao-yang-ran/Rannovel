"""RanNovel common interface."""
from __future__ import annotations
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox, QPushButton
SOURCE_LABELS = {"character": "人物", "location": "地点", "event": "事件", "setting": "设定", "inspiration": "灵感"}
NAV = [("write", "正文写作"), ("inspiration", "灵感库"), ("character", "人物与关系"),
       ("graph", "人物关系图"), ("event", "故事时间线"), ("setting", "世界观设定"),
       ("location", "地理图鉴")]


def button(text, callback, layout=None):
    item = QPushButton(text)
    item.clicked.connect(callback)
    if layout is not None: layout.addWidget(item)
    return item


def menu_button(text, actions, layout=None):
    """Keep secondary actions close to their list without crowding the toolbar."""
    item = QPushButton(text)
    menu = QMenu(item)
    for label, callback in actions:
        if label is None:
            menu.addSeparator()
        else:
            menu.addAction(label, callback)
    item.setMenu(menu)
    if layout is not None: layout.addWidget(item)
    return item


def ask_text(parent, title, label, old=""):
    value, ok = QInputDialog.getText(parent, title, label, text=old)
    return value.strip() if ok and value.strip() else None


def show_error(parent, error):
    QMessageBox.critical(parent, "操作失败", str(error))
