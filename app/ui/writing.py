"""RanNovel writing interface."""
from __future__ import annotations
import re
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPlainTextEdit, QListWidget, QListWidgetItem, QMessageBox, QSpinBox, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
from app.ui.dialogs import SaveDialog, pick_record
from app.services.repository import KINDS, TARGET_PERMISSIONS
from app.ui.common import SOURCE_LABELS, button, menu_button, ask_text, show_error
from app.ui.media import ImageTextEdit


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
            item = QListWidgetItem(f"{SOURCE_LABELS.get(ref.source_kind, '未知资料')} · {name}")
            item.setData(Qt.ItemDataRole.UserRole, ("reference", ref.id)); self.list.addItem(item)
        for inspiration in inspirations:
            item = QListWidgetItem(f"灵感 · {inspiration.content[:70]}")
            item.setData(Qt.ItemDataRole.UserRole, ("inspiration", inspiration.id)); self.list.addItem(item)
    def add(self):
        allowed = sorted(TARGET_PERMISSIONS[self.target_kind])
        display = [SOURCE_LABELS[k] for k in allowed]
        label, ok = QInputDialog.getItem(self, "关联资料", "选择类型", display, 0, False)
        if not ok:
            return
        kind = allowed[display.index(label)]
        def load(query, limit, offset):
            if kind == "inspiration":
                rows = self.repo.available_inspirations(self.work_id, query, limit, offset)
                return [(row.id, f"#{row.id} {row.content[:100]}") for row in rows]
            rows = self.repo.list_entities(kind, None if kind == "character" else self.work_id,
                                           query=query, limit=limit, offset=offset)
            return [(row.id, f"#{row.id} {row.name}") for row in rows]
        item_id = pick_record(self, "关联" + SOURCE_LABELS[kind], load)
        if item_id is None:
            return
        try:
            if kind == "inspiration":
                self.repo.assign_inspiration(item_id, self.work_id, self.target_kind, self.target_id)
            else:
                self.repo.add_reference(self.target_kind, self.target_id, kind, item_id)
            self.refresh()
        except Exception as error:
            show_error(self, error)

    def remove(self):
        item = self.list.currentItem()
        if not item: return
        kind, item_id = item.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "解除关联", "解除此处的关联？") != QMessageBox.StandardButton.Yes: return
        try:
            if kind == "inspiration": self.repo.detach_inspiration(item_id)
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
        self.font_box = QFontComboBox(); self.font_box.currentFontChanged.connect(lambda f: self.editor.setCurrentFont(f)); toolbar.addWidget(self.font_box)
        self.font_size = QSpinBox(); self.font_size.setRange(8, 72); self.font_size.setValue(14)
        self.font_size.valueChanged.connect(lambda n: self.editor.setFontPointSize(n)); toolbar.addWidget(self.font_size)
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
        self.count_timer = QTimer(self); self.count_timer.setSingleShot(True); self.count_timer.setInterval(200)
        self.count_timer.timeout.connect(lambda: self.words.setText(f"{self.word_count()} 字"))
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
        if self.target_id is None:
            QMessageBox.information(self, "选择章节", "请先选择要插入图片的章节。")
            return
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
        if not self.find_text.text():
            return
        edit_block = self.editor.textCursor()
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        edit_block.beginEditBlock()
        try:
            while True:
                cursor = self.editor.document().find(self.find_text.text(), cursor)
                if cursor.isNull():
                    break
                cursor.insertText(self.replace_text.text())
        finally:
            edit_block.endEditBlock()
    def word_count(self): return len(re.sub(r"[\s\uFFFC]+", "", self.editor.toPlainText()))
    def changed(self):
        if self.target_id is None:
            return
        self.dirty = True
        self.save_error = False
        self.count_timer.start()
        self.status.setText("未保存 · 自动保存中…")
        self.timer.start()

    def save_now(self):
        if not self.dirty or self.target_id is None: return True
        self.timer.stop()
        try:
            self.repo.save_body(self.target_kind, self.target_id, self.editor.toHtml(), self.word_count())
            self.count_timer.stop()
            self.words.setText(f"{self.word_count()} 字")
            self.dirty = False; self.save_error = False; self.status.setText("已保存")
            return True
        except Exception as error:
            self.save_error = True; self.status.setText("保存失败 · 请重试")
            show_error(self, error); return False
    def load_target(self, kind, item_id):
        if not self.save_now():
            return False
        try:
            body = self.repo.get_body(kind, item_id)
            refs = ReferencePanel(self.repo, kind, item_id, self.work_id)
        except Exception as error:
            show_error(self, error)
            return False
        self.editor.blockSignals(True)
        self.editor.clear()
        self.editor.document().setBaseUrl(QUrl.fromLocalFile(str(self.repo.paths.data_dir) + "/"))
        self.editor.setHtml(body.body_html or "")
        self.editor.blockSignals(False)
        self.editor.reset_asset_protection()
        self.target_kind, self.target_id = kind, item_id
        self.dirty = self.save_error = False
        self.status.setText("已保存")
        self.words.setText(f"{self.word_count()} 字")
        missing = self.repo.missing_body_images(kind, item_id)
        if missing:
            self.status.setText("图片文件缺失 · 请从备份恢复或移除引用")
            QMessageBox.warning(self, "正文图片缺失", "以下受管理图片找不到：\n" + "\n".join(missing))
        if self.refs:
            self.refs.setParent(None)
            self.refs.deleteLater()
        self.refs = refs
        self.editor.parentWidget().layout().addWidget(self.refs)
        self.editor.setEnabled(True)
        return True

    def refresh_outline(self):
        selected = self.selected_outline() or (("chapter", self.target_id) if self.target_id else None)
        expanded = {self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole):
                    self.tree.topLevelItem(i).isExpanded() for i in range(self.tree.topLevelItemCount())}
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            for volume in self.repo.list_volumes(self.work_id):
                key = ("volume", volume.id)
                parent = QTreeWidgetItem([volume.title, volume.summary, ""])
                parent.setData(0, Qt.ItemDataRole.UserRole, key)
                self.tree.addTopLevelItem(parent)
                if key == selected:
                    self.tree.setCurrentItem(parent)
                for chapter in volume.chapters:
                    child = QTreeWidgetItem([chapter.title, chapter.core_events or chapter.summary, str(chapter.estimated_words)])
                    child.setData(0, Qt.ItemDataRole.UserRole, ("chapter", chapter.id))
                    parent.addChild(child)
                    if ("chapter", chapter.id) == selected:
                        self.tree.setCurrentItem(child)
                parent.setExpanded(expanded.get(key, True))
        finally:
            self.tree.blockSignals(False)
        self.editor.setEnabled(self.target_id is not None)

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
        if not item:
            return
        kind, item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if kind == "chapter" and item_id != self.target_id:
            if not self.load_target("chapter", item_id):
                self.tree.blockSignals(True)
                self.tree.setCurrentItem(None)
                self.tree.blockSignals(False)
                self.refresh_outline()

    def dispose(self):
        self.timer.stop()
        self.count_timer.stop()
        self.repo.release_assets(self.editor.asset_owner)

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
        dialog = SaveDialog(self); dialog.setWindowTitle("大纲详情"); dialog.resize(480, 330)
        form = QFormLayout(dialog)
        summary = QPlainTextEdit(item.summary); form.addRow("概述", summary)
        core = words = None
        if kind == "chapter":
            core = QPlainTextEdit(item.core_events); form.addRow("核心事件", core)
            words = QSpinBox(); words.setRange(0, 10000000); words.setValue(item.estimated_words); form.addRow("目标字数", words)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dialog.accept); box.rejected.connect(dialog.reject); form.addRow(box)
        dialog.save_action = lambda: self.repo.update_outline_details(
            kind, item_id, summary.toPlainText(), core.toPlainText() if core else "", words.value() if words else 0)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_outline()

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
