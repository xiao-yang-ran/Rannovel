"""Reusable searchable selectors, validated forms, and background operations."""
from __future__ import annotations

from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QPushButton, QVBoxLayout,
)


class SaveDialog(QDialog):
    """Keep the user's form open if validation or persistence fails."""
    save_action = None

    def accept(self):
        try:
            if self.save_action is not None:
                self.save_action()
        except Exception as error:
            QMessageBox.critical(self, "保存失败", str(error))
            return
        super().accept()


class RecordPicker(QDialog):
    def __init__(self, parent, title, loader):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(580, 450)
        self.loader = loader
        self.offset = 0
        self.selected_id = None
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("输入名称或内容搜索")
        layout.addWidget(self.search)
        self.items = QListWidget()
        layout.addWidget(self.items)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.more = QPushButton("加载更多")
        self.more.clicked.connect(self.load_more)
        layout.addWidget(self.more)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.items.itemDoubleClicked.connect(lambda _: self.accept())
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.search.textChanged.connect(lambda: self.timer.start())
        self.timer.timeout.connect(self.refresh)
        self.refresh()

    def refresh(self):
        self.offset = 0
        self.items.clear()
        self.load_more()

    def load_more(self):
        try:
            rows = self.loader(self.search.text(), 100, self.offset)
        except Exception as error:
            self.status.setText(str(error))
            self.more.setVisible(False)
            return
        for item_id, label in rows:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, item_id)
            self.items.addItem(item)
        self.offset += len(rows)
        self.more.setVisible(len(rows) == 100)
        self.status.setText(f"已显示 {self.offset} 项" if self.offset else "没有匹配的条目。")

    def accept(self):
        # Do not accept stale results while the debounce timer is still pending.
        if self.timer.isActive():
            self.timer.stop()
            self.refresh()
            return
        item = self.items.currentItem()
        if item is not None:
            self.selected_id = item.data(Qt.ItemDataRole.UserRole)
            super().accept()


def pick_record(parent, title, loader):
    dialog = RecordPicker(parent, title, loader)
    return dialog.selected_id if dialog.exec() == QDialog.DialogCode.Accepted else None


def parse_custom_fields(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        marks = [mark for mark in ("：", "=", ":") if mark in line]
        if not marks:
            raise ValueError("补充信息每行需包含分隔符，例如：喜好：喝茶。")
        mark = min(marks, key=line.index)
        key, value = line.split(mark, 1)
        key = key.strip()
        if not key or key in result:
            raise ValueError("补充信息的名称不能为空或重复。")
        result[key] = value.strip()
    return result


class _Worker(QThread):
    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation
        self.result = self.error = None

    def run(self):
        try:
            self.result = self.operation()
        except Exception as error:
            self.error = error


class _JobDialog(QDialog):
    def reject(self):
        if self.worker.isFinished():
            super().reject()

    def closeEvent(self, event):
        if not self.worker.isFinished():
            event.ignore()
        else:
            event.accept()


def run_job(parent, title, operation):
    dialog = _JobDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setMinimumWidth(360)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(title + "，请稍候…"))
    progress = QProgressBar()
    progress.setRange(0, 0)
    layout.addWidget(progress)
    worker = dialog.worker = _Worker(operation, dialog)
    worker.finished.connect(dialog.accept)
    # Start after the nested event loop starts, including for extremely fast jobs.
    QTimer.singleShot(0, worker.start)
    dialog.exec()
    worker.wait()
    if worker.error is not None:
        raise worker.error
    return worker.result
