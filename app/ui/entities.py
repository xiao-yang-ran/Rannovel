"""RanNovel entities interface."""
from __future__ import annotations
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPlainTextEdit, QListWidget, QListWidgetItem, QMessageBox, QScrollArea, QSpinBox, QVBoxLayout, QWidget
from app.ui.dialogs import SaveDialog, parse_custom_fields, pick_record
from app.ui.common import SOURCE_LABELS, button, menu_button, ask_text, show_error
from app.ui.media import image_controls, attach_images


class EntityPage(QWidget):
    def __init__(self, repo, kind, work_id=None):
        super().__init__(); self.repo, self.kind, self.work_id = repo, kind, work_id
        layout = QVBoxLayout(self); layout.addWidget(QLabel(SOURCE_LABELS[kind] + (" · 当前长篇" if kind != "character" else " · 全局共享")))
        row = QHBoxLayout(); layout.addLayout(row)
        self.search = QLineEdit(); self.search.setPlaceholderText("搜索名称和内容"); row.addWidget(self.search)
        if kind in ("location", "setting"):
            self.category_filter = QComboBox(); row.addWidget(self.category_filter)
            self.category_filter.currentIndexChanged.connect(lambda _: self.refresh(False))
        self.debounce = QTimer(self); self.debounce.setSingleShot(True); self.debounce.setInterval(300)
        self.search.textChanged.connect(lambda: self.debounce.start()); self.debounce.timeout.connect(lambda: self.refresh(False))
        button("新增", self.add, row); button("编辑", self.edit, row)
        actions = [("查看引用位置", self.usages)]
        if kind == "event": actions.append(("管理事件人物", self.manage_event_people))
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
        dialog = SaveDialog(self); dialog.setWindowTitle("编辑" + SOURCE_LABELS[self.kind]); dialog.resize(650, 620)
        outer = QVBoxLayout(dialog); scroll = QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        inner = QWidget(); scroll.setWidget(inner); form = QFormLayout(inner)
        name = QLineEdit(old.name if old else ""); form.addRow("名称", name)
        details = QPlainTextEdit(old.details if old else ""); details.setMaximumHeight(80); form.addRow("详情", details)
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
            editor = QPlainTextEdit(str(getattr(old, field, "")) if old else ""); editor.setMaximumHeight(75)
            form.addRow(label, editor); extra_widgets[field] = editor
        if self.kind in ("character", "setting"):
            custom = QPlainTextEdit("\n".join(f"{k}：{v}" for k, v in (old.custom_fields or {}).items()) if old else "")
            custom.setPlaceholderText("每行写一项，例如：喜好：喝茶")
            custom.setMaximumHeight(90); form.addRow("补充信息", custom); extra_widgets["custom_fields"] = custom
        if self.kind == "character":
            faction = QComboBox(); faction.addItem("未归属", None)
            for item in self.repo.list_factions(): faction.addItem(f"{item.name} · {item.kind}", item.id)
            faction.setCurrentIndex(max(0, faction.findData(old.faction_id if old else None)))
            form.addRow("阵营", faction); extra_widgets["faction_id"] = faction
        year = month = None
        if self.kind == "event":
            year = QSpinBox(); year.setRange(-9999, 9999); year.setValue(old.year if old else 1); form.addRow("年份", year)
            month = QSpinBox(); month.setRange(1, 12); month.setValue(old.month if old else 1); form.addRow("月份", month)
        pending_images = image_controls(form, self.repo, self.kind, item_id, dialog) if self.kind in ("character", "location") else []
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dialog.accept); box.rejected.connect(dialog.reject); outer.addWidget(box)
        saved = {}
        def save():
            values = {"name": name.text(), "details": details.toPlainText()}
            for field, widget in extra_widgets.items():
                values[field] = (widget.currentData() if field == "faction_id" else
                                 widget.currentText() if field == "category" else widget.toPlainText())
            if "custom_fields" in values:
                values["custom_fields"] = parse_custom_fields(values["custom_fields"])
            if year:
                values.update(year=year.value(), month=month.value())
            saved["id"] = self.repo.save_entity(self.kind, item_id, self.work_id, **values)
        dialog.save_action = save
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = saved["id"]
            self.refresh()
            if self.kind == "event":
                self.edit_event_people(new_id)
            if pending_images:
                try:
                    attach_images(self.repo, self.kind, new_id, pending_images)
                except Exception as error:
                    show_error(self, f"条目已保存，但部分图片未能添加：{error}")

    def edit_event_people(self, event_id):
        def load(query, limit, offset):
            return [(p.id, f"#{p.id} {p.name}") for p in
                    self.repo.list_entities("character", query=query, limit=limit, offset=offset)]
        person_id = pick_record(self, "关联事件人物", load)
        if person_id is not None:
            try:
                self.repo.link_event_character(event_id, person_id)
            except Exception as error:
                show_error(self, error)

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
    def delete(self):
        item_id = self.selected_id()
        if item_id and QMessageBox.question(self, "删除资料", "永久删除所选资料？已有引用或图库图片时会拒绝删除。") == QMessageBox.StandardButton.Yes:
            try: self.repo.delete_entity(self.kind, item_id); self.refresh()
            except Exception as error: show_error(self, error)
    def refresh_relations(self):
        self.relations.clear()
        names = self.repo.character_names()
        for rel in self.repo.list_relations():
            item = QListWidgetItem(f"{names.get(rel.source_id, '?')} —{rel.relation_type}→ {names.get(rel.target_id, '?')}  {rel.details}")
            item.setData(Qt.ItemDataRole.UserRole, rel.id); self.relations.addItem(item)
    def add_relation(self):
        def load(query, limit, offset):
            return [(p.id, f"#{p.id} {p.name}") for p in
                    self.repo.list_entities("character", query=query, limit=limit, offset=offset)]
        first = pick_record(self, "选择起点人物", load)
        if first is None:
            return
        second = pick_record(self, "选择终点人物", load)
        if second is None:
            return
        kind = ask_text(self, "添加关系", "关系名称")
        if kind:
            try:
                self.repo.add_relation(first, second, kind)
                self.refresh_relations()
            except Exception as error:
                show_error(self, error)

    def delete_relation(self):
        item = self.relations.currentItem()
        if item and QMessageBox.question(self, "删除关系", "删除所选人物关系？") == QMessageBox.StandardButton.Yes:
            try:
                self.repo.delete_relation(item.data(Qt.ItemDataRole.UserRole))
                self.refresh_relations()
            except Exception as error:
                show_error(self, error)
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
