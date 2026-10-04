"""RanNovel graph interface."""
from __future__ import annotations
import math
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QLabel, QLineEdit, QMessageBox, QVBoxLayout, QWidget


class GraphView(QGraphicsView):
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        if 0.02 <= self.transform().m11() * factor <= 10:
            self.scale(factor, factor)
        event.accept()


class RelationGraph(QWidget):
    def __init__(self, repo):
        super().__init__(); self.repo = repo
        layout = QVBoxLayout(self); layout.addWidget(QLabel("人物关系图 · 点击查看详情，拖动画布，滚轮缩放"))
        self.scene = QGraphicsScene(self); self.view = GraphView(self.scene); self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(self.view); self.view.mousePressEvent = self.clicked
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索人物；单次显示最多 200 人")
        layout.insertWidget(1, self.search)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(300)
        self.search.textChanged.connect(lambda: self.debounce.start())
        self.debounce.timeout.connect(self.refresh)
        self.refresh()
    def refresh(self):
        self.scene.clear()
        people = self.repo.list_entities("character", query=self.search.text(), limit=201)
        self.status.setText("匹配超过 200 人，请缩小搜索范围。" if len(people) > 200 else f"显示 {len(people)} 人")
        people = people[:200]
        relations = self.repo.list_relations([person.id for person in people])
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
