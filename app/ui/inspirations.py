"""RanNovel inspirations interface."""
from __future__ import annotations
from PySide6.QtCore import QMimeData, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QListWidget, QListWidgetItem, QMessageBox, QTabWidget, QVBoxLayout, QWidget
from app.ui.dialogs import SaveDialog, pick_record
from app.services.repository import KINDS
from app.ui.common import button, menu_button, show_error
from app.ui.media import image_controls, attach_images


def edit_inspiration(parent, repo, item_id=None):
    old = repo.get_inspiration(item_id) if item_id is not None else None
    if item_id is not None and old is None:
        show_error(parent, "灵感已不存在。")
        return False
    dialog = SaveDialog(parent)
    dialog.setWindowTitle("编辑灵感" if old else "新建灵感")
    dialog.resize(620, 380)
    form = QFormLayout(dialog)
    content = QPlainTextEdit(old.content if old else "")
    form.addRow("内容", content)
    tags = QLineEdit(old.tags if old else "")
    form.addRow("标签", tags)
    pool = None
    if old is None:
        pool = QComboBox()
        pool.addItem("随笔池", "essay")
        pool.addItem("长篇池（片段也使用此池）", "novel")
        form.addRow("来源池", pool)
    pending_images = image_controls(form, repo, "inspiration", item_id, dialog)
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    form.addRow(box)
    saved = {}
    def save():
        if old is None:
            saved["id"] = repo.add_inspiration(content.toPlainText(), tags.text(), pool.currentData())
        else:
            repo.update_inspiration(item_id, content.toPlainText(), tags.text())
            saved["id"] = item_id
    dialog.save_action = save
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    if pending_images:
        try:
            attach_images(repo, "inspiration", saved["id"], pending_images)
        except Exception as error:
            show_error(parent, f"灵感已保存，但部分图片未能添加：{error}")
    return True


def inspiration_marker():
    pixmap = QPixmap(22, 22); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#64879A"), 2)); painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(5, 5, 12, 12)); painter.end()
    return QIcon(pixmap)


class InspirationList(QListWidget):
    dropped_on_self = Signal(int, int)
    use_requested = Signal(int)
    def __init__(self):
        super().__init__(); self.setDragEnabled(True); self.setAcceptDrops(True)
        self.setObjectName("inspirationPool"); self.setIconSize(QSize(22, 22))
        self.use_icon = inspiration_marker()
    def mouseReleaseEvent(self, event):
        item = self.itemAt(event.pos())
        if (event.button() == Qt.MouseButton.LeftButton and item and
                event.pos().x() <= self.visualItemRect(item).left() + 42):
            self.setCurrentItem(item)
            self.use_requested.emit(item.data(Qt.ItemDataRole.UserRole))
            event.accept(); return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return) and self.currentItem():
            self.use_requested.emit(self.currentItem().data(Qt.ItemDataRole.UserRole))
            event.accept(); return
        super().keyPressEvent(event)
    def startDrag(self, _actions):
        item = self.currentItem()
        if not item: return
        data = QMimeData(); data.setData("application/x-rannovel-inspiration", str(item.data(Qt.ItemDataRole.UserRole)).encode())
        drag = QDrag(self); drag.setMimeData(data); drag.exec(Qt.DropAction.MoveAction)
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-rannovel-inspiration"): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-rannovel-inspiration"): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event):
        if event.source() == self and event.mimeData().hasFormat("application/x-rannovel-inspiration"):
            source = int(bytes(event.mimeData().data("application/x-rannovel-inspiration")))
            target_item = self.itemAt(event.position().toPoint())
            if target_item: self.dropped_on_self.emit(source, target_item.data(Qt.ItemDataRole.UserRole))
            event.acceptProposedAction()
        else: event.ignore()


class InspirationPage(QWidget):
    def __init__(self, repo, current_work_id):
        super().__init__(); self.repo, self.current_work_id = repo, current_work_id
        layout = QVBoxLayout(self); layout.addWidget(QLabel("待用灵感 · 点击条目前的圆圈归属作品"))
        row = QHBoxLayout(); layout.addLayout(row)
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索全部灵感的内容和标签"); row.addWidget(self.search)
        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(300)
        self.search.textChanged.connect(lambda: self.debounce.start()); self.debounce.timeout.connect(self.refresh)
        button("新建灵感", self.add, row); button("编辑", self.edit, row)
        menu_button("更多操作", [("标记为已使用…", self.assign_selected),
                                ("上移", lambda: self.move(-1)), ("下移", lambda: self.move(1)),
                                (None, None), ("删除所选…", self.delete)], row)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs, 1)
        self.lists = {}; self.more_buttons = {}; self.offsets = {}
        self._selected_id = None
        for key, label in (("essay", "随笔池"), ("novel", "长篇池（含片段）")):
            panel = QWidget(); panel_layout = QVBoxLayout(panel)
            view = InspirationList(); panel_layout.addWidget(view, 1)
            view.itemClicked.connect(lambda item: setattr(self, "_selected_id", item.data(Qt.ItemDataRole.UserRole)))
            view.currentItemChanged.connect(lambda item, previous: setattr(self, "_selected_id", item.data(Qt.ItemDataRole.UserRole)) if item else None)
            view.itemDoubleClicked.connect(lambda _: self.edit())
            view.dropped_on_self.connect(self.drag_reorder)
            view.use_requested.connect(self.use_item)
            self.lists[key] = view
            self.more_buttons[key] = button("加载更多", lambda checked=False, k=key: self.load_more(k), panel_layout)
            self.tabs.addTab(panel, label)
        self.tabs.currentChanged.connect(self.clear_selection)
        self.refresh()
    def clear_selection(self, _index):
        self._selected_id = None
        for view in self.lists.values(): view.clearSelection()
    def refresh(self):
        self._selected_id = None
        for key, view in self.lists.items():
            view.clear()
            self.offsets[key] = 0
            self.load_more(key)
    def load_more(self, key):
        view = self.lists[key]
        items = self.repo.list_inspirations(self.search.text(), key, False, limit=200, offset=self.offsets[key])
        for item in items:
            label = " ".join(item.content.split())[:140]
            if item.tags: label += f"  ·  #{item.tags}"
            row = QListWidgetItem(view.use_icon, label)
            row.setData(Qt.ItemDataRole.UserRole, item.id)
            row.setToolTip("点击左侧圆圈标记为已使用；双击编辑。\n" + item.content)
            row.setSizeHint(QSize(0, 48)); view.addItem(row)
        self.offsets[key] += len(items)
        self.more_buttons[key].setVisible(len(items) == 200)
    def selected_id(self):
        return self._selected_id
    def add(self):
        if edit_inspiration(self, self.repo): self.refresh()
    def edit(self):
        item_id = self.selected_id()
        if item_id and edit_inspiration(self, self.repo, item_id): self.refresh()
    def assign_selected(self):
        if self.selected_id(): self.use_item(self.selected_id())
    def use_item(self, item_id):
        item = self.repo.get_inspiration(item_id)
        if item is None:
            return
        pool = item.pool
        works = [work for work in self.repo.list_works()
                 if (work.kind == "essay") == (pool == "essay")]
        current_id = self.current_work_id()
        current = self.repo.get_work(current_id) if current_id else None
        if current and (current.kind == "essay") == (pool == "essay"):
            work_id = current.id
        elif not works:
            QMessageBox.information(self, "没有匹配作品", "请先创建与此灵感池对应的作品。")
            return
        elif len(works) == 1:
            work_id = works[0].id
        else:
            def load(query, limit, offset):
                rows = [work for work in works if query.strip().casefold() in work.title.casefold()]
                return [(work.id, f"#{work.id} {KINDS[work.kind]} · {work.title}") for work in rows[offset:offset+limit]]
            work_id = pick_record(self, "选择归属作品", load)
            if work_id is None:
                return
        self.assign(item_id, work_id)

    def assign(self, item_id, work_id):
        try: self.repo.assign_inspiration(item_id, work_id); self.refresh()
        except Exception as error: show_error(self, error)
    def move(self, direction):
        if self.selected_id():
            try: self.repo.reorder_inspiration(self.selected_id(), direction); self.refresh()
            except Exception as error: show_error(self, error)
    def drag_reorder(self, source_id, target_id):
        try: self.repo.move_inspiration_before(source_id, target_id); self.refresh()
        except Exception as error: show_error(self, error)
    def delete(self):
        if self.selected_id() and QMessageBox.question(self, "删除灵感", "永久删除所选灵感？") == QMessageBox.StandardButton.Yes:
            try: self.repo.delete_inspiration(self.selected_id()); self.refresh()
            except Exception as error: show_error(self, error)


class UsedInspirationDialog(QDialog):
    def __init__(self, repo, parent=None):
        super().__init__(parent); self.repo = repo
        self.setWindowTitle("已使用灵感"); self.resize(760, 580)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("已归属作品的灵感 · 可编辑或放回待用池"))
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索内容和标签"); layout.addWidget(self.search)
        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(300)
        self.search.textChanged.connect(lambda: self.debounce.start()); self.debounce.timeout.connect(self.refresh)
        self.list = QListWidget(); self.list.setObjectName("usedInspirationList"); layout.addWidget(self.list, 1)
        self.list.itemDoubleClicked.connect(lambda _: self.edit())
        self.more = button("加载更多", self.load_more, layout)
        row = QHBoxLayout(); layout.addLayout(row)
        button("编辑及配图", self.edit, row); button("查看引用", self.usages, row)
        button("放回待用池…", self.unassign, row); button("关闭", self.accept, row)
        self.refresh()
    def refresh(self):
        self.offset = 0; self.list.clear(); self.load_more()
    def load_more(self):
        items = self.repo.list_inspirations(self.search.text(), used=True, limit=200, offset=self.offset)
        for item in items:
            label = " ".join(item.content.split())[:130]
            if item.tags: label += f"  ·  #{item.tags}"
            label += f"  →  {item.owner.title}" if item.owner else ""
            row = QListWidgetItem(label); row.setData(Qt.ItemDataRole.UserRole, item.id)
            row.setToolTip(item.content); row.setSizeHint(QSize(0, 48)); self.list.addItem(row)
        self.offset += len(items); self.more.setVisible(len(items) == 200)
    def selected_id(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None
    def edit(self):
        if self.selected_id() and edit_inspiration(self, self.repo, self.selected_id()): self.refresh()
    def usages(self):
        if self.selected_id():
            uses = self.repo.usages("inspiration", self.selected_id())
            QMessageBox.information(self, "引用位置", "\n".join(f"{kind} #{item_id}" for kind, item_id in uses)
                                    if uses else "已归属作品，尚未关联具体正文。")
    def unassign(self):
        if self.selected_id() and QMessageBox.question(self, "放回待用池", "解除作品和正文关联，并放回待用池？") == QMessageBox.StandardButton.Yes:
            try: self.repo.unassign_inspiration(self.selected_id()); self.refresh()
            except Exception as error: show_error(self, error)
