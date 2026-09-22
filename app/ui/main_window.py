"""RanNovel desktop workspace. Pages are created only when first opened."""
from __future__ import annotations

import math
import re
from pathlib import Path
from PySide6.QtCore import QMimeData, QPointF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QIcon, QImage, QPainter, QPen, QPixmap, QTextCursor, QTextImageFormat
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFontComboBox, QFormLayout, QFrame, QGraphicsScene, QGraphicsView, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QStackedWidget, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from app.models import Inspiration
from app.services.backup_service import create_backup, restore_backup
from app.services.repository import KINDS, TARGET_PERMISSIONS
from app.ui.decor import HeroPanel

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


class ImageTextEdit(QTextEdit):
    image_added = Signal(str)
    def __init__(self, repo, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setAcceptDrops(True)
        self.document().setBaseUrl(QUrl.fromLocalFile(str(repo.paths.data_dir) + "/"))

    def canInsertFromMimeData(self, source):
        return bool(source.hasUrls() and any(u.isLocalFile() for u in source.urls())) or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasUrls():
            paths = [u.toLocalFile() for u in source.urls() if u.isLocalFile()]
            if paths:
                for path in paths: self.insert_image(path)
                return
        super().insertFromMimeData(source)

    def insert_image(self, path):
        try:
            _, relative = self.repo.import_image(path)
            fmt = QTextImageFormat()
            fmt.setName(relative)
            image = QImage(str(self.repo.paths.data_dir / relative))
            if image.isNull(): raise ValueError("图片无法读取。")
            if image.width() > 680: fmt.setWidth(680); fmt.setHeight(680 * image.height() / image.width())
            self.textCursor().insertImage(fmt)
            self.image_added.emit(relative)
        except Exception as error: show_error(self, error)


class GalleryList(QListWidget):
    files_dropped = Signal(list)
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setIconSize(QSize(96, 72))
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths: self.files_dropped.emit(paths); event.acceptProposedAction()
        else: super().dropEvent(event)


class GalleryDialog(QDialog):
    def __init__(self, repo, kind, source_id, parent=None):
        super().__init__(parent)
        self.repo, self.kind, self.source_id = repo, kind, source_id
        self.setWindowTitle("图库 · 可拖入本地图片")
        self.resize(550, 430)
        layout = QVBoxLayout(self)
        self.list = GalleryList(); layout.addWidget(self.list)
        self.list.files_dropped.connect(self.add_paths)
        self.list.itemDoubleClicked.connect(self.preview)
        row = QHBoxLayout(); layout.addLayout(row)
        button("添加图片…", self.select_files, row)
        button("移除选中图片", self.remove_selected, row)
        button("关闭", self.accept, row)
        self.refresh()
    def refresh(self):
        self.list.clear()
        for link, path in self.repo.gallery(self.kind, self.source_id):
            item = QListWidgetItem(path.name if path.exists() else f"文件丢失：{path.name}")
            item.setData(Qt.ItemDataRole.UserRole, link.id)
            if path.exists(): item.setIcon(QIcon(QPixmap(str(path)).scaled(96, 72, Qt.AspectRatioMode.KeepAspectRatio)))
            self.list.addItem(item)
    def select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "添加本地图片", str(Path.home()), "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        self.add_paths(paths)
    def add_paths(self, paths):
        for path in paths:
            try:
                asset_id, _ = self.repo.import_image(path)
                self.repo.add_gallery_image(self.kind, self.source_id, asset_id)
            except Exception as error: show_error(self, error)
        self.refresh()
    def remove_selected(self):
        item = self.list.currentItem()
        if item and QMessageBox.question(self, "移除图片", "从此图库移除所选图片？") == QMessageBox.StandardButton.Yes:
            self.repo.remove_gallery_image(item.data(Qt.ItemDataRole.UserRole)); self.refresh()
    def preview(self, item):
        for link, path in self.repo.gallery(self.kind, self.source_id):
            if link.id != item.data(Qt.ItemDataRole.UserRole): continue
            if not path.exists(): show_error(self, FileNotFoundError(path)); return
            dialog = QDialog(self); dialog.setWindowTitle(path.name); dialog.resize(800, 600)
            layout = QVBoxLayout(dialog); label = QLabel(); label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setPixmap(QPixmap(str(path)).scaled(760, 540, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(label); button("关闭", dialog.accept, layout); dialog.exec(); return


class ReferencePanel(QWidget):
    def __init__(self, repo, target_kind, target_id, work_id, parent=None):
        super().__init__(parent)
        self.repo, self.target_kind, self.target_id, self.work_id = repo, target_kind, target_id, work_id
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("关联资料"))
        self.list = QListWidget(); layout.addWidget(self.list)
        row = QHBoxLayout(); layout.addLayout(row)
        button("添加关联", self.add, row); button("解除关联", self.remove, row)
        self.refresh()
    def refresh(self):
        self.list.clear()
        refs, inspirations = self.repo.references_for(self.target_kind, self.target_id)
        for ref, name in refs:
            item = QListWidgetItem(f"{SOURCE_LABELS[ref.source_kind]} · {name}")
            item.setData(Qt.ItemDataRole.UserRole, ("reference", ref.id)); self.list.addItem(item)
        for inspiration in inspirations:
            item = QListWidgetItem(f"灵感 · {inspiration.content[:70]}")
            item.setData(Qt.ItemDataRole.UserRole, ("inspiration", inspiration.id)); self.list.addItem(item)
    def add(self):
        allowed = sorted(TARGET_PERMISSIONS[self.target_kind])
        display = [SOURCE_LABELS[k] for k in allowed]
        label, ok = QInputDialog.getItem(self, "关联资料", "选择类型", display, 0, False)
        if not ok: return
        kind = allowed[display.index(label)]
        query, ok = QInputDialog.getText(self, "查找资料", "名称、灵感内容或标签（可留空）")
        if not ok: return
        if kind == "inspiration":
            options = self.repo.available_inspirations(self.work_id, query)
            names = [f"#{i.id} {i.content[:70]}" for i in options]
        else:
            options = self.repo.list_entities(kind, None if kind == "character" else self.work_id, query=query, limit=200)
            names = [f"#{i.id} {i.name}" for i in options]
        if not names: QMessageBox.information(self, "暂无可关联资料", "请先创建可用资料。"); return
        selected, ok = QInputDialog.getItem(self, "关联资料", "选择条目", names, 0, False)
        if not ok: return
        item_id = options[names.index(selected)].id
        try:
            if kind == "inspiration": self.repo.assign_inspiration(item_id, self.work_id, self.target_kind, self.target_id)
            else: self.repo.add_reference(self.target_kind, self.target_id, kind, item_id)
            self.refresh()
        except Exception as error: show_error(self, error)
    def remove(self):
        item = self.list.currentItem()
        if not item: return
        kind, item_id = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "解除关联", "解除此处的关联？") != QMessageBox.StandardButton.Yes: return
        try:
            if kind == "inspiration": self.repo.unassign_inspiration(item_id)
            else: self.repo.remove_reference(item_id)
            self.refresh()
        except Exception as error: show_error(self, error)


class WritingPage(QWidget):
    def __init__(self, repo, work_id, parent=None):
        super().__init__(parent)
        self.repo, self.work_id = repo, work_id
        self.work = repo.get_work(work_id)
        self.target_kind = None; self.target_id = None; self.dirty = False; self.save_error = False
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(800); self.timer.timeout.connect(self.save_now)
        layout = QVBoxLayout(self)
        heading = QHBoxLayout(); layout.addLayout(heading)
        heading.addWidget(QLabel(f"{KINDS[self.work.kind]} · {self.work.title}"))
        self.status = QLabel("选择正文开始写作" if self.work.kind == "novel" else "已保存")
        heading.addStretch(); heading.addWidget(self.status)
        splitter = QSplitter(); layout.addWidget(splitter, 1)
        if self.work.kind == "novel":
            left = QWidget(); l = QVBoxLayout(left)
            row = QHBoxLayout(); l.addLayout(row)
            button("新建卷", self.add_volume, row); button("新建章", self.add_chapter, row)
            menu_button("大纲操作", [("改名", self.rename_outline), ("编辑详情", self.outline_details),
                                  ("上移", lambda: self.move_outline(-1)),
                                  ("下移", lambda: self.move_outline(1)),
                                  (None, None), ("删除空项…", self.delete_outline)], row)
            self.tree = QTreeWidget(); self.tree.setColumnCount(3)
            self.tree.setHeaderLabels(["分卷 / 章节", "概述 / 核心事件", "目标字数"]); l.addWidget(self.tree)
            self.tree.itemSelectionChanged.connect(self.select_chapter)
            splitter.addWidget(left)
        right = QWidget(); r = QVBoxLayout(right); splitter.addWidget(right)
        toolbar = QHBoxLayout(); r.addLayout(toolbar)
        self.font = QFontComboBox(); self.font.currentFontChanged.connect(lambda f: self.editor.setCurrentFont(f)); toolbar.addWidget(self.font)
        self.size = QSpinBox(); self.size.setRange(8, 72); self.size.setValue(14)
        self.size.valueChanged.connect(lambda n: self.editor.setFontPointSize(n)); toolbar.addWidget(self.size)
        for label, hint, callback in [("B", "粗体", self.toggle_bold), ("I", "斜体", self.toggle_italic),
                                      ("U", "下划线", self.toggle_underline)]:
            control = button(label, callback, toolbar)
            control.setObjectName("compactButton"); control.setToolTip(hint); control.setAccessibleName(hint)
        menu_button("对齐", [("左对齐", lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignLeft)),
                             ("居中", lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignHCenter))], toolbar)
        button("插入图片", self.select_image, toolbar)
        find_row = QHBoxLayout(); r.addLayout(find_row)
        self.find_text = QLineEdit(); self.find_text.setPlaceholderText("查找"); find_row.addWidget(self.find_text)
        self.replace_text = QLineEdit(); self.replace_text.setPlaceholderText("替换为"); find_row.addWidget(self.replace_text)
        button("查找下一个", self.find_next, find_row)
        menu_button("替换", [("替换当前并查找下一个", self.replace_one), ("全部替换", self.replace_all)], find_row)
        self.editor = ImageTextEdit(repo); self.editor.setPlaceholderText("在这里写正文…")
        self.editor.textChanged.connect(self.changed); r.addWidget(self.editor, 1)
        foot = QHBoxLayout(); r.addLayout(foot)
        self.words = QLabel("0 字"); foot.addWidget(self.words); foot.addStretch()
        button("立即保存", self.save_now, foot)
        self.refs = None
        if self.work.kind != "novel": self.load_target(self.work.kind, work_id)
        else: self.refresh_outline()
        splitter.setStretchFactor(1, 4)
    def toggle_bold(self): self.editor.setFontWeight(QFont.Weight.Normal if self.editor.fontWeight() >= QFont.Weight.Bold else QFont.Weight.Bold)
    def toggle_italic(self): self.editor.setFontItalic(not self.editor.fontItalic())
    def toggle_underline(self): self.editor.setFontUnderline(not self.editor.fontUnderline())
    def select_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "插入本地图片", str(Path.home()), "图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if path: self.editor.insert_image(path)
    def find_next(self):
        needle = self.find_text.text()
        if needle and not self.editor.find(needle):
            cursor = self.editor.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.Start); self.editor.setTextCursor(cursor)
            self.editor.find(needle)
    def replace_one(self):
        if self.editor.textCursor().selectedText() == self.find_text.text() and self.find_text.text():
            self.editor.textCursor().insertText(self.replace_text.text())
        self.find_next()
    def replace_all(self):
        if not self.find_text.text(): return
        cursor = self.editor.textCursor(); cursor.beginEditBlock(); cursor.movePosition(QTextCursor.MoveOperation.Start)
        while True:
            cursor = self.editor.document().find(self.find_text.text(), cursor)
            if cursor.isNull(): break
            cursor.insertText(self.replace_text.text())
        cursor.endEditBlock()
    def word_count(self): return len(re.sub(r"\s+", "", self.editor.toPlainText()))
    def changed(self):
        if self.target_id is None: return
        self.dirty = True; self.save_error = False
        self.words.setText(f"{self.word_count()} 字")
        self.status.setText("未保存 · 自动保存中…"); self.timer.start()
    def save_now(self):
        if not self.dirty or self.target_id is None: return True
        self.timer.stop()
        try:
            self.repo.save_body(self.target_kind, self.target_id, self.editor.toHtml(), self.word_count())
            self.dirty = False; self.save_error = False; self.status.setText("已自动保存")
            return True
        except Exception as error:
            self.save_error = True; self.status.setText("保存失败 · 请重试")
            show_error(self, error); return False
    def load_target(self, kind, item_id):
        if not self.save_now(): return False
        self.target_kind, self.target_id = kind, item_id
        body = self.repo.get_body(kind, item_id)
        self.editor.blockSignals(True)
        self.editor.clear(); self.editor.document().setBaseUrl(QUrl.fromLocalFile(str(self.repo.paths.data_dir) + "/"))
        self.editor.setHtml(body.body_html or "")
        self.editor.blockSignals(False)
        self.dirty = False; self.status.setText("已保存"); self.words.setText(f"{self.word_count()} 字")
        missing = self.repo.missing_body_images(kind, item_id)
        if missing:
            self.status.setText("图片文件缺失 · 请从备份恢复或移除引用")
            QMessageBox.warning(self, "正文图片缺失", "以下受管理图片找不到：\n" + "\n".join(missing))
        if self.refs:
            self.refs.setParent(None)
            self.refs.deleteLater()
        self.refs = ReferencePanel(self.repo, kind, item_id, self.work_id)
        right = self.editor.parentWidget()
        right.layout().addWidget(self.refs)
        self.editor.setEnabled(True)
        return True
    def refresh_outline(self):
        self.tree.clear()
        for volume in self.repo.list_volumes(self.work_id):
            parent = QTreeWidgetItem([volume.title, volume.summary, ""]); parent.setData(0, Qt.ItemDataRole.UserRole, ("volume", volume.id)); self.tree.addTopLevelItem(parent)
            for chapter in volume.chapters:
                child = QTreeWidgetItem([chapter.title, chapter.core_events or chapter.summary, str(chapter.estimated_words)])
                child.setData(0, Qt.ItemDataRole.UserRole, ("chapter", chapter.id)); parent.addChild(child)
            parent.setExpanded(True)
        if self.target_id is None: self.editor.setEnabled(False)
    def add_volume(self):
        title = ask_text(self, "新建分卷", "卷名")
        if title:
            try: self.repo.add_volume(self.work_id, title); self.refresh_outline()
            except Exception as error: show_error(self, error)
    def add_chapter(self):
        item = self.tree.currentItem()
        if item is None: QMessageBox.information(self, "选择分卷", "先选择一卷。"); return
        kind, item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if kind == "chapter": item_id = item.parent().data(0, Qt.ItemDataRole.UserRole)[1]
        title = ask_text(self, "新建章节", "章名")
        if title:
            try:
                chapter_id = self.repo.add_chapter(item_id, title); self.refresh_outline()
                for i in range(self.tree.topLevelItemCount()):
                    parent = self.tree.topLevelItem(i)
                    for j in range(parent.childCount()):
                        child = parent.child(j)
                        if child.data(0, Qt.ItemDataRole.UserRole) == ("chapter", chapter_id): self.tree.setCurrentItem(child)
            except Exception as error: show_error(self, error)
    def select_chapter(self):
        item = self.tree.currentItem()
        if not item: return
        kind, item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if kind == "chapter" and item_id != self.target_id:
            if not self.load_target("chapter", item_id):
                self.tree.blockSignals(True); self.tree.clearSelection(); self.tree.blockSignals(False)
    def selected_outline(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None
    def rename_outline(self):
        selected = self.selected_outline()
        if not selected: return
        kind, item_id = selected
        title = ask_text(self, "卷章改名", "新名称", self.tree.currentItem().text(0))
        if title:
            try: self.repo.rename_outline(kind, item_id, title); self.refresh_outline()
            except Exception as error: show_error(self, error)
    def outline_details(self):
        selected = self.selected_outline()
        if not selected: return
        kind, item_id = selected
        item = None
        for volume in self.repo.list_volumes(self.work_id):
            if kind == "volume" and volume.id == item_id: item = volume
            if kind == "chapter": item = next((chapter for chapter in volume.chapters if chapter.id == item_id), item)
        if item is None: return
        dialog = QDialog(self); dialog.setWindowTitle("大纲详情"); dialog.resize(480, 330)
        form = QFormLayout(dialog)
        summary = QTextEdit(item.summary); form.addRow("概述", summary)
        core = words = None
        if kind == "chapter":
            core = QTextEdit(item.core_events); form.addRow("核心事件", core)
            words = QSpinBox(); words.setRange(0, 10000000); words.setValue(item.estimated_words); form.addRow("目标字数", words)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dialog.accept); box.rejected.connect(dialog.reject); form.addRow(box)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.repo.update_outline_details(kind, item_id, summary.toPlainText(),
                                                 core.toPlainText() if core else "", words.value() if words else 0)
                self.refresh_outline()
            except Exception as error: show_error(self, error)
    def move_outline(self, direction):
        selected = self.selected_outline()
        if not selected: return
        try: self.repo.move_outline(*selected, direction); self.refresh_outline()
        except Exception as error: show_error(self, error)
    def delete_outline(self):
        selected = self.selected_outline()
        if not selected or not self.save_now(): return
        if QMessageBox.question(self, "删除空项", "仅允许删除没有正文或引用的空章节、空分卷。确认删除？") != QMessageBox.StandardButton.Yes: return
        try:
            self.repo.delete_outline(*selected)
            if selected == ("chapter", self.target_id):
                self.target_kind = self.target_id = None
                self.editor.clear(); self.editor.setEnabled(False)
                if self.refs: self.refs.setParent(None); self.refs.deleteLater(); self.refs = None
            self.refresh_outline()
        except Exception as error: show_error(self, error)


class EntityPage(QWidget):
    def __init__(self, repo, kind, work_id=None):
        super().__init__(); self.repo, self.kind, self.work_id = repo, kind, work_id
        layout = QVBoxLayout(self); layout.addWidget(QLabel(SOURCE_LABELS[kind] + (" · 当前长篇" if kind != "character" else " · 全局共享")))
        row = QHBoxLayout(); layout.addLayout(row)
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索名称"); row.addWidget(self.search)
        if kind in ("location", "setting"):
            self.category_filter = QComboBox(); row.addWidget(self.category_filter)
            self.category_filter.currentIndexChanged.connect(lambda _: self.refresh(False))
        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(300)
        self.search.textChanged.connect(lambda: self.debounce.start()); self.debounce.timeout.connect(lambda: self.refresh(False))
        button("新增", self.add, row); button("编辑", self.edit, row)
        actions = [("查看引用位置", self.usages)]
        if kind == "event": actions.append(("管理事件人物", self.manage_event_people))
        if kind in ("character", "location"): actions.append(("打开图库", self.gallery))
        actions.extend([(None, None), ("删除所选…", self.delete)])
        menu_button("更多操作", actions, row)
        self.list = QListWidget(); layout.addWidget(self.list)
        self.list.itemDoubleClicked.connect(lambda _: self.edit())
        self.more = button("加载更多", self.load_more, layout)
        if kind == "character":
            layout.addWidget(QLabel("人物关系"))
            relrow = QHBoxLayout(); layout.addLayout(relrow)
            menu_button("关系操作", [("添加关系", self.add_relation), ("编辑关系", self.edit_relation),
                                   (None, None), ("删除关系…", self.delete_relation)], relrow)
            self.relations = QListWidget(); layout.addWidget(self.relations)
            layout.addWidget(QLabel("势力阵营"))
            faction_row = QHBoxLayout(); layout.addLayout(faction_row)
            menu_button("阵营操作", [("新增阵营", self.add_faction), ("编辑阵营", self.edit_faction),
                                   (None, None), ("删除阵营…", self.delete_faction)], faction_row)
            self.factions = QListWidget(); layout.addWidget(self.factions)
        self.offset = 0; self.refresh()
    def refresh(self, include_auxiliary=True):
        if include_auxiliary and self.kind in ("location", "setting"):
            previous = self.category_filter.currentData()
            self.category_filter.blockSignals(True); self.category_filter.clear()
            self.category_filter.addItem("全部分类", None)
            for category in self.repo.list_categories(self.kind, self.work_id): self.category_filter.addItem(category, category)
            self.category_filter.setCurrentIndex(max(0, self.category_filter.findData(previous)))
            self.category_filter.blockSignals(False)
        self.offset = 0; self.list.clear(); self.load_more()
        if include_auxiliary and self.kind == "character": self.refresh_relations(); self.refresh_factions()
    def load_more(self):
        category = self.category_filter.currentData() if self.kind in ("location", "setting") else None
        rows = self.repo.list_entities(self.kind, self.work_id, self.search.text(), 100, self.offset, category)
        for item in rows:
            label = (f"{item.name} · {item.year}年{item.month}月" if self.kind == "event" else
                     f"{item.category} · {item.name}" if self.kind in ("location", "setting") else item.name)
            entry = QListWidgetItem(label); entry.setData(Qt.ItemDataRole.UserRole, item.id); self.list.addItem(entry)
        self.offset += len(rows); self.more.setVisible(len(rows) == 100)
    def selected_id(self):
        item = self.list.currentItem(); return item.data(Qt.ItemDataRole.UserRole) if item else None
    def add(self): self.edit_item(None)
    def edit(self):
        if self.selected_id(): self.edit_item(self.selected_id())
    def edit_item(self, item_id):
        old = self.repo.get_entity(self.kind, item_id) if item_id else None
        dialog = QDialog(self); dialog.setWindowTitle("编辑" + SOURCE_LABELS[self.kind]); dialog.resize(650, 620)
        outer = QVBoxLayout(dialog); scroll = QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        inner = QWidget(); scroll.setWidget(inner); form = QFormLayout(inner)
        name = QLineEdit(old.name if old else ""); form.addRow("名称", name)
        details = QTextEdit(old.details if old else ""); details.setMaximumHeight(80); form.addRow("详情", details)
        extra_widgets = {}
        if self.kind in ("location", "setting"):
            category = QComboBox(); category.setEditable(True)
            category.addItems(("区域", "国家", "城市", "地貌", "建筑", "遗迹", "路线", "地点") if self.kind == "location" else
                              ("世界总纲", "战力体系", "能量与魔法", "种族", "文明", "政治", "宗教", "经济", "历史", "文化", "语言"))
            category.setCurrentText(old.category if old else ("地点" if self.kind == "location" else "世界总纲"))
            form.addRow("分类", category); extra_widgets["category"] = category
        fields = ({"character": (("personality", "性格"), ("motivation", "动机"), ("skills", "能力"), ("background", "背景")),
                   "location": (("layout", "空间布局"), ("environment_rules", "环境规则"), ("physical_laws", "物理法则"), ("notes", "备注")),
                   "setting": (("overview", "概述"), ("structure", "结构"), ("rules", "规则"), ("advancement", "进阶"),
                               ("limitations", "限制"), ("relationships", "关联"), ("notes", "备注"))})
        for field, label in fields.get(self.kind, ()):
            editor = QTextEdit(str(getattr(old, field, "")) if old else ""); editor.setMaximumHeight(75)
            form.addRow(label, editor); extra_widgets[field] = editor
        if self.kind in ("character", "setting"):
            custom = QTextEdit("\n".join(f"{k}={v}" for k, v in (old.custom_fields or {}).items()) if old else "")
            custom.setMaximumHeight(90); form.addRow("自定义字段（每行 键=值）", custom); extra_widgets["custom_fields"] = custom
        if self.kind == "character":
            faction = QComboBox(); faction.addItem("未归属", None)
            for item in self.repo.list_factions(): faction.addItem(f"{item.name} · {item.kind}", item.id)
            faction.setCurrentIndex(max(0, faction.findData(old.faction_id if old else None)))
            form.addRow("阵营", faction); extra_widgets["faction_id"] = faction
        year = month = None
        if self.kind == "event":
            year = QSpinBox(); year.setRange(-9999, 9999); year.setValue(old.year if old else 1); form.addRow("年份", year)
            month = QSpinBox(); month.setRange(1, 12); month.setValue(old.month if old else 1); form.addRow("月份", month)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dialog.accept); box.rejected.connect(dialog.reject); outer.addWidget(box)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                values = {"name": name.text(), "details": details.toPlainText()}
                for field, widget in extra_widgets.items():
                    values[field] = (widget.currentData() if field == "faction_id" else
                                     widget.currentText() if field == "category" else widget.toPlainText())
                if "custom_fields" in values:
                    custom_fields = {}
                    for line in values["custom_fields"].splitlines():
                        if "=" in line:
                            key, value = line.split("=", 1)
                            if key.strip(): custom_fields[key.strip()] = value.strip()
                    values["custom_fields"] = custom_fields
                if year: values.update(year=year.value(), month=month.value())
                new_id = self.repo.save_entity(self.kind, item_id, self.work_id, **values)
                self.refresh()
                if self.kind == "event": self.edit_event_people(new_id)
            except Exception as error: show_error(self, error)
    def edit_event_people(self, event_id):
        people = self.repo.list_entities("character", limit=500)
        if not people: return
        choices = [f"#{p.id} {p.name}" for p in people]
        choice, ok = QInputDialog.getItem(self, "事件人物", "关联人物（可稍后继续添加）", ["暂不添加"] + choices, 0, False)
        if ok and choice != "暂不添加":
            try: self.repo.link_event_character(event_id, people[choices.index(choice)].id)
            except Exception as error: show_error(self, error)
    def manage_event_people(self):
        event_id = self.selected_id()
        if not event_id: return
        action, ok = QInputDialog.getItem(self, "事件人物", "操作", ["关联人物", "解除人物关联"], 0, False)
        if not ok: return
        if action == "关联人物": self.edit_event_people(event_id); return
        people = self.repo.event_characters(event_id)
        if not people: QMessageBox.information(self, "事件人物", "此事件尚未关联人物。"); return
        labels = [f"#{person.id} {person.name}" for person in people]
        chosen, ok = QInputDialog.getItem(self, "解除关联", "选择人物", labels, 0, False)
        if ok:
            try: self.repo.unlink_event_character(event_id, people[labels.index(chosen)].id)
            except Exception as error: show_error(self, error)
    def usages(self):
        item_id = self.selected_id()
        if not item_id: return
        uses = self.repo.usages(self.kind, item_id)
        if self.kind == "event":
            people = self.repo.event_characters(item_id)
            suffix = "\n关联人物：" + "、".join(p.name for p in people)
        else: suffix = ""
        QMessageBox.information(self, "引用位置", "\n".join(f"{kind} #{i}" for kind, i in uses) + suffix if uses or suffix else "尚无引用。")
    def gallery(self):
        if self.selected_id(): GalleryDialog(self.repo, self.kind, self.selected_id(), self).exec()
    def delete(self):
        item_id = self.selected_id()
        if item_id and QMessageBox.question(self, "删除资料", "永久删除所选资料？已有引用或图库图片时会拒绝删除。") == QMessageBox.StandardButton.Yes:
            try: self.repo.delete_entity(self.kind, item_id); self.refresh()
            except Exception as error: show_error(self, error)
    def refresh_relations(self):
        self.relations.clear()
        names = {c.id: c.name for c in self.repo.list_entities("character", limit=10000)}
        for rel in self.repo.list_relations():
            item = QListWidgetItem(f"{names.get(rel.source_id, '?')} —{rel.relation_type}→ {names.get(rel.target_id, '?')}  {rel.details}")
            item.setData(Qt.ItemDataRole.UserRole, rel.id); self.relations.addItem(item)
    def add_relation(self):
        people = self.repo.list_entities("character", limit=10000)
        if len(people) < 2: QMessageBox.information(self, "人物不足", "至少需要两个人物。"); return
        names = [f"#{p.id} {p.name}" for p in people]
        first, ok = QInputDialog.getItem(self, "添加关系", "起点人物", names, 0, False)
        if not ok: return
        second, ok = QInputDialog.getItem(self, "添加关系", "终点人物", names, 1, False)
        if not ok: return
        kind = ask_text(self, "添加关系", "关系名称")
        if kind:
            try: self.repo.add_relation(people[names.index(first)].id, people[names.index(second)].id, kind); self.refresh_relations()
            except Exception as error: show_error(self, error)
    def delete_relation(self):
        item = self.relations.currentItem()
        if item and QMessageBox.question(self, "删除关系", "删除所选人物关系？") == QMessageBox.StandardButton.Yes:
            self.repo.delete_relation(item.data(Qt.ItemDataRole.UserRole)); self.refresh_relations()
    def refresh_factions(self):
        self.factions.clear()
        for faction in self.repo.list_factions():
            item = QListWidgetItem(f"{faction.name} · {faction.kind}  {faction.description[:70]}")
            item.setData(Qt.ItemDataRole.UserRole, faction.id); self.factions.addItem(item)
    def selected_faction(self):
        item = self.factions.currentItem(); return item.data(Qt.ItemDataRole.UserRole) if item else None
    def add_faction(self): self.edit_faction_item(None)
    def edit_faction(self):
        if self.selected_faction(): self.edit_faction_item(self.selected_faction())
    def edit_faction_item(self, faction_id):
        old = next((f for f in self.repo.list_factions() if f.id == faction_id), None)
        name = ask_text(self, "阵营", "名称", old.name if old else "")
        if not name: return
        kind = ask_text(self, "阵营", "类型", old.kind if old else "阵营")
        if not kind: return
        details, ok = QInputDialog.getMultiLineText(self, "阵营", "描述", old.description if old else "")
        if ok:
            try: self.repo.save_faction(faction_id, name, kind, details); self.refresh_factions()
            except Exception as error: show_error(self, error)
    def delete_faction(self):
        faction_id = self.selected_faction()
        if faction_id and QMessageBox.question(self, "删除阵营", "删除所选阵营？有成员时会拒绝删除。") == QMessageBox.StandardButton.Yes:
            try: self.repo.delete_faction(faction_id); self.refresh_factions()
            except Exception as error: show_error(self, error)
    def edit_relation(self):
        item = self.relations.currentItem()
        if not item: return
        relation = next((r for r in self.repo.list_relations() if r.id == item.data(Qt.ItemDataRole.UserRole)), None)
        if not relation: return
        name = ask_text(self, "编辑关系", "关系名称", relation.relation_type)
        if not name: return
        details, ok = QInputDialog.getMultiLineText(self, "编辑关系", "详情", relation.details)
        if ok:
            try: self.repo.update_relation(relation.id, name, details); self.refresh_relations()
            except Exception as error: show_error(self, error)


class InspirationList(QListWidget):
    dropped_on_self = Signal(int, int)
    def __init__(self):
        super().__init__(); self.setDragEnabled(True); self.setAcceptDrops(True)
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


class WorkDropList(QListWidget):
    assigned = Signal(int, int)
    def __init__(self):
        super().__init__(); self.setAcceptDrops(True)
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-rannovel-inspiration"): event.acceptProposedAction()
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-rannovel-inspiration"): event.acceptProposedAction()
    def dropEvent(self, event):
        target = self.itemAt(event.position().toPoint())
        if target:
            item_id = int(bytes(event.mimeData().data("application/x-rannovel-inspiration")))
            self.assigned.emit(item_id, target.data(Qt.ItemDataRole.UserRole)); event.acceptProposedAction()


class InspirationPage(QWidget):
    def __init__(self, repo):
        super().__init__(); self.repo = repo
        layout = QVBoxLayout(self); layout.addWidget(QLabel("全局灵感库 · 拖到右侧作品即可归属"))
        row = QHBoxLayout(); layout.addLayout(row)
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索全部灵感的内容和标签"); row.addWidget(self.search)
        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(300)
        self.search.textChanged.connect(lambda: self.debounce.start()); self.debounce.timeout.connect(lambda: self.refresh(False))
        button("新建灵感", self.add, row); button("编辑", self.edit, row)
        button("归属作品…", self.assign_selected, row)
        menu_button("更多操作", [("打开图库", self.gallery), ("查看引用位置", self.usages),
                                (None, None), ("上移", lambda: self.move(-1)),
                                ("下移", lambda: self.move(1)), (None, None),
                                ("解除归属…", self.unassign), ("删除所选…", self.delete)], row)
        split = QSplitter(); layout.addWidget(split, 1)
        pools = QWidget(); pl = QVBoxLayout(pools); split.addWidget(pools)
        self.lists = {}; self.more_buttons = {}; self.offsets = {}
        self._selected_id = None
        for key, label in (("essay", "随笔池 · 待用"), ("novel", "长篇池 · 待用"), ("used", "已使用 · 两池合并")):
            pl.addWidget(QLabel(label)); view = InspirationList(); pl.addWidget(view)
            view.itemClicked.connect(lambda item: setattr(self, "_selected_id", item.data(Qt.ItemDataRole.UserRole)))
            view.currentItemChanged.connect(lambda item, previous: setattr(self, "_selected_id", item.data(Qt.ItemDataRole.UserRole)) if item else None)
            if key != "used": view.dropped_on_self.connect(self.drag_reorder)
            self.lists[key] = view
            self.more_buttons[key] = button("加载更多", lambda checked=False, k=key: self.load_more(k), pl)
        target_panel = QWidget(); tl = QVBoxLayout(target_panel); split.addWidget(target_panel)
        tl.addWidget(QLabel("拖拽目标 · 放到作品上")); self.targets = WorkDropList(); tl.addWidget(self.targets)
        self.targets.assigned.connect(self.assign)
        split.setStretchFactor(0, 3); split.setStretchFactor(1, 1)
        self.refresh()
    def refresh(self, include_targets=True):
        self._selected_id = None
        for key, view in self.lists.items():
            view.clear()
            self.offsets[key] = 0
            self.load_more(key)
        if include_targets: self.refresh_targets()
    def refresh_targets(self):
        self.targets.clear()
        for work in self.repo.list_works():
            row = QListWidgetItem(f"{KINDS[work.kind]} · {work.title}")
            row.setData(Qt.ItemDataRole.UserRole, work.id); self.targets.addItem(row)
    def load_more(self, key):
        view = self.lists[key]
        items = self.repo.list_inspirations(self.search.text(), None if key == "used" else key,
                                            key == "used", limit=200, offset=self.offsets[key])
        for item in items:
            owner = item.owner
            label = f"[{'随笔池' if item.pool == 'essay' else '长篇池'}] {item.content[:100]}  #{item.tags}"
            if owner: label += f"  → {owner.title}"
            row = QListWidgetItem(label); row.setData(Qt.ItemDataRole.UserRole, item.id); view.addItem(row)
        self.offsets[key] += len(items)
        self.more_buttons[key].setVisible(len(items) == 200)
    def selected_id(self):
        return self._selected_id
    def get_item(self, item_id):
        with self.repo.database.session_factory() as s: return s.get(Inspiration, item_id)
    def add(self):
        dialog = QDialog(self); dialog.setWindowTitle("新建灵感"); form = QFormLayout(dialog)
        content = QTextEdit(); form.addRow("内容", content)
        tags = QLineEdit(); form.addRow("标签", tags)
        pool = QComboBox(); pool.addItem("随笔池", "essay"); pool.addItem("长篇池（片段也使用此池）", "novel"); form.addRow("来源池", pool)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dialog.accept); box.rejected.connect(dialog.reject); form.addRow(box)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try: self.repo.add_inspiration(content.toPlainText(), tags.text(), pool.currentData()); self.refresh()
            except Exception as error: show_error(self, error)
    def edit(self):
        item_id = self.selected_id()
        if not item_id: return
        item = self.get_item(item_id)
        content, ok = QInputDialog.getMultiLineText(self, "编辑灵感", "内容", item.content)
        if not ok: return
        tags, ok = QInputDialog.getText(self, "编辑标签", "标签", text=item.tags)
        if ok:
            try: self.repo.update_inspiration(item_id, content, tags); self.refresh()
            except Exception as error: show_error(self, error)
    def gallery(self):
        if self.selected_id(): GalleryDialog(self.repo, "inspiration", self.selected_id(), self).exec()
    def assign_selected(self):
        item_id = self.selected_id()
        if not item_id: return
        works = self.repo.list_works(); labels = [f"{KINDS[w.kind]} · {w.title}" for w in works]
        if not labels: QMessageBox.information(self, "没有作品", "请先新建作品。"); return
        label, ok = QInputDialog.getItem(self, "归属灵感", "作品", labels, 0, False)
        if ok: self.assign(item_id, works[labels.index(label)].id)
    def assign(self, item_id, work_id):
        try: self.repo.assign_inspiration(item_id, work_id); self.refresh(); QMessageBox.information(self, "归属完成", "灵感已移入已使用。")
        except Exception as error: show_error(self, error)
    def usages(self):
        if self.selected_id():
            uses = self.repo.usages("inspiration", self.selected_id())
            QMessageBox.information(self, "引用位置", "\n".join(f"{kind} #{i}" for kind, i in uses) if uses else "已归属作品，尚未关联具体正文。")
    def move(self, direction):
        if self.selected_id():
            try: self.repo.reorder_inspiration(self.selected_id(), direction); self.refresh()
            except Exception as error: show_error(self, error)
    def drag_reorder(self, source_id, target_id):
        try: self.repo.move_inspiration_before(source_id, target_id); self.refresh()
        except Exception as error: show_error(self, error)
    def unassign(self):
        if self.selected_id() and QMessageBox.question(self, "解除归属", "解除作品和正文关联，并放回待用池？") == QMessageBox.StandardButton.Yes:
            self.repo.unassign_inspiration(self.selected_id()); self.refresh()
    def delete(self):
        if self.selected_id() and QMessageBox.question(self, "删除灵感", "永久删除所选灵感？") == QMessageBox.StandardButton.Yes:
            try: self.repo.delete_inspiration(self.selected_id()); self.refresh()
            except Exception as error: show_error(self, error)


class GraphView(QGraphicsView):
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        event.accept()


class RelationGraph(QWidget):
    def __init__(self, repo):
        super().__init__(); self.repo = repo
        layout = QVBoxLayout(self); layout.addWidget(QLabel("人物关系图 · 点击查看详情，拖动画布，滚轮缩放"))
        self.scene = QGraphicsScene(self); self.view = GraphView(self.scene); self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(self.view); self.view.mousePressEvent = self.clicked
        self.refresh()
    def refresh(self):
        self.scene.clear()
        people = self.repo.list_entities("character", limit=10000); relations = self.repo.list_relations()
        positions = {}
        for n, person in enumerate(people):
            ring, slot = divmod(n, 12)
            count = min(12, len(people) - ring * 12)
            angle = 2 * math.pi * slot / max(1, count)
            radius = 0 if len(people) == 1 else 180 + 130 * ring
            positions[person.id] = QPointF(radius * math.cos(angle), radius * math.sin(angle))
        for rel in relations:
            a, b = positions.get(rel.source_id), positions.get(rel.target_id)
            if a is None or b is None: continue
            line = self.scene.addLine(a.x(), a.y(), b.x(), b.y(), QPen(QColor("#8e765c"), 2)); line.setData(0, ("relation", rel.id))
            mid = (a+b)/2; label = self.scene.addText(rel.relation_type); label.setPos(mid); label.setData(0, ("relation", rel.id))
        for person in people:
            p = positions[person.id]; node = self.scene.addEllipse(p.x()-36, p.y()-36, 72, 72, QPen(QColor("#294866"), 2), QColor("#dbe7ed"))
            node.setData(0, ("character", person.id)); node.setZValue(2)
            label = self.scene.addText(person.name); label.setPos(p.x()-35, p.y()-12); label.setData(0, ("character", person.id)); label.setZValue(3)
        extent = 320 + 130 * max(0, (len(people) - 1) // 12)
        self.scene.setSceneRect(-extent, -extent, 2 * extent, 2 * extent)
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    def clicked(self, event):
        item = self.view.itemAt(event.pos())
        if item and item.data(0):
            kind, item_id = item.data(0)
            if kind == "character":
                person = self.repo.get_entity("character", item_id)
                detail = "\n".join(line for line in (
                    person.details, f"性格：{person.personality}" if person.personality else "",
                    f"动机：{person.motivation}" if person.motivation else "",
                    f"能力：{person.skills}" if person.skills else "",
                    f"背景：{person.background}" if person.background else "") if line)
                QMessageBox.information(self, person.name, detail or "暂无详情")
            else:
                relation = next((r for r in self.repo.list_relations() if r.id == item_id), None)
                if relation: QMessageBox.information(self, relation.relation_type, relation.details or "暂无详情")
        QGraphicsView.mousePressEvent(self.view, event)


class MainWindow(QMainWindow):
    def __init__(self, repo, paths):
        super().__init__(); self.repo, self.paths = repo, paths
        self.setWindowTitle("RanNovel · 一间写故事的书房"); self.resize(1400, 900)
        self.current_work_id = None; self.page_cache = {}
        central = QWidget(); root = QHBoxLayout(central); self.setCentralWidget(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(225)
        side_layout = QVBoxLayout(sidebar)
        brand = QLabel("RanNovel"); brand.setObjectName("brand"); side_layout.addWidget(brand)
        subtitle = QLabel("一间写故事的书房"); subtitle.setObjectName("subtitle"); side_layout.addWidget(subtitle)
        side_layout.addSpacing(24)
        label = QLabel("创 作 空 间"); label.setObjectName("navSection"); side_layout.addWidget(label)
        self.navigation = QListWidget(); self.navigation.setObjectName("navigation")
        for _, label in NAV: self.navigation.addItem(label)
        side_layout.addWidget(self.navigation, 1)
        notice = QLabel("● 离线创作 · 数据仅在本机"); notice.setObjectName("localNotice"); side_layout.addWidget(notice)
        root.addWidget(sidebar)
        content = QWidget(); content.setObjectName("contentSurface")
        content_layout = QVBoxLayout(content)
        self.hero = HeroPanel(); content_layout.addWidget(self.hero)
        self.pages = QStackedWidget(); content_layout.addWidget(self.pages, 1)
        root.addWidget(content, 1)
        self.navigation.currentRowChanged.connect(self.change_page)
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction("立即备份…", self.backup)
        file_menu.addAction("从 ZIP 恢复…", self.restore)
        file_menu.addSeparator(); file_menu.addAction("退出", self.close)
        self.work_menu = self.menuBar().addMenu("作品")
        self.rebuild_work_menu()
        works = repo.list_works()
        if works: self.current_work_id = works[0].id
        self.navigation.setCurrentRow(0)
        self.statusBar().showMessage("完全离线 · 数据保存在 AppData")
    def rebuild_work_menu(self):
        self.work_menu.clear()
        self.work_menu.addAction("新建作品…", self.new_work)
        self.work_menu.addAction("打开作品…", self.open_work)
        self.work_menu.addAction("归档当前作品", self.archive_current)
        self.work_menu.addAction("查看归档作品…", self.open_archived)
        self.work_menu.addAction("恢复当前作品到常用列表", self.restore_current)
        self.work_menu.addSeparator()
        for work in self.repo.list_works():
            self.work_menu.addAction(f"{KINDS[work.kind]} · {work.title}", lambda checked=False, i=work.id: self.switch_work(i))
    def new_work(self):
        title = ask_text(self, "新建作品", "作品名称")
        if not title: return
        kinds = ["长篇", "随笔", "片段"]
        label, ok = QInputDialog.getItem(self, "写作模式", "选择模式", kinds, 0, False)
        if ok:
            try:
                work_id = self.repo.create_work(title, list(KINDS)[kinds.index(label)])
                if not self.switch_work(work_id): self.rebuild_work_menu()
            except Exception as error: show_error(self, error)
    def open_work(self): self.choose_work(False)
    def open_archived(self): self.choose_work(True)
    def choose_work(self, archived):
        works = self.repo.list_works(archived); labels = [f"{KINDS[w.kind]} · {w.title}" for w in works]
        if not works: QMessageBox.information(self, "作品", "列表为空。"); return
        label, ok = QInputDialog.getItem(self, "归档作品" if archived else "打开作品", "选择作品", labels, 0, False)
        if ok: self.switch_work(works[labels.index(label)].id)
    def archive_current(self):
        if self.current_work_id and self.flush_editor():
            old_id = self.current_work_id
            self.repo.archive_work(old_id, True); self._discard_work_pages(old_id); self.current_work_id = None
            self.rebuild_work_menu(); self.show_current()
    def restore_current(self):
        if self.current_work_id:
            self.repo.archive_work(self.current_work_id, False); self.rebuild_work_menu()
    def flush_editor(self):
        for page in self.page_cache.values():
            if isinstance(page, WritingPage) and not page.save_now(): return False
        return True
    def _discard_work_pages(self, work_id):
        for key, page in list(self.page_cache.items()):
            if key[1] == work_id:
                self.pages.removeWidget(page); page.deleteLater(); del self.page_cache[key]
    def switch_work(self, work_id):
        if not self.flush_editor(): return False
        old_id = self.current_work_id
        if old_id is not None and old_id != work_id:
            self._discard_work_pages(old_id)
        self.current_work_id = work_id; self.show_current(); self.rebuild_work_menu()
        work = self.repo.get_work(work_id)
        self.statusBar().showMessage(f"正在编辑：{work.title}" + (" · 已归档" if work.archived else ""))
        return True
    def change_page(self, index):
        if index >= 0:
            self.hero.title.setText(NAV[index][1])
            self.hero.subline.setText("在这里继续写下你的故事。")
            self.show_current()
    def show_current(self):
        index = self.navigation.currentRow()
        if index < 0: return
        kind = NAV[index][0]
        work = self.repo.get_work(self.current_work_id) if self.current_work_id else None
        created = False
        if kind in {"write", "event", "setting", "location"} and not work:
            key = ("empty", None)
            if key not in self.page_cache:
                label = QLabel("从左上角“作品”新建或打开作品。")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.page_cache[key] = label; self.pages.addWidget(label)
        elif kind in {"event", "setting", "location"} and work.kind != "novel":
            key = ("novel_only", None)
            if key not in self.page_cache:
                label = QLabel("此资料按长篇独立保存；请选择长篇作品。")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.page_cache[key] = label; self.pages.addWidget(label)
        else:
            key = (kind, self.current_work_id if kind in {"write", "event", "setting", "location"} else None)
            created = key not in self.page_cache
            if created:
                page = (WritingPage(self.repo, work.id) if kind == "write" else
                        InspirationPage(self.repo) if kind == "inspiration" else
                        RelationGraph(self.repo) if kind == "graph" else
                        EntityPage(self.repo, kind, work.id if kind != "character" else None))
                self.page_cache[key] = page; self.pages.addWidget(page)
        page = self.page_cache[key]
        if not created and not isinstance(page, WritingPage) and hasattr(page, "refresh"): page.refresh()
        self.pages.setCurrentWidget(page)
    def backup(self):
        if not self.flush_editor(): return
        folder = QFileDialog.getExistingDirectory(self, "选择备份目录", str(self.paths.backup_dir))
        if folder:
            try:
                output = create_backup(self.paths.database_file, Path(folder), self.paths.assets_dir)
                QMessageBox.information(self, "备份完成", str(output))
            except Exception as error: show_error(self, error)
    def restore(self):
        if not self.flush_editor(): return
        file, _ = QFileDialog.getOpenFileName(self, "选择备份", str(self.paths.backup_dir), "ZIP (*.zip)")
        if not file: return
        if QMessageBox.question(self, "确认恢复", "恢复将替换当前资料；程序会先创建安全备份。继续吗？") != QMessageBox.StandardButton.Yes: return
        try:
            for timer in self.findChildren(QTimer): timer.stop()
            safety = restore_backup(Path(file), self.repo.database, self.paths.backup_dir, self.paths.assets_dir)
            for page in self.page_cache.values():
                self.pages.removeWidget(page); page.deleteLater()
            self.page_cache.clear(); self.current_work_id = None
            works = self.repo.list_works(); self.current_work_id = works[0].id if works else None
            self.rebuild_work_menu(); self.show_current()
            QMessageBox.information(self, "恢复完成", f"安全备份：{safety}")
        except Exception as error: show_error(self, error)
    def closeEvent(self, event):
        if self.flush_editor():
            for timer in self.findChildren(QTimer): timer.stop()
            event.accept()
        else: event.ignore()
