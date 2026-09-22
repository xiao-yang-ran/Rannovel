"""Tiny code-native ornaments; no external assets or network needed."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


SECTION_COPY = (
    ("灵感摘录", "先收下句子，再让它找到自己的故事。"),
    ("故事年表", "把时间写清楚，命运才有回响。"),
    ("人物群像", "每个人都有不肯说出口的来处。"),
    ("世界法则", "为想象设定边界，也给奇迹留下入口。"),
    ("山川地理", "让每一处地方都能容纳一个故事。"),
    ("章节脉络", "从一页纸开始，铺开完整的长篇。"),
)


def navigation_icon(kind: int) -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#E3D0A9"), 1.7))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == 0:  # a folded note
        painter.drawRoundedRect(QRectF(6, 5, 20, 22), 3, 3)
        painter.drawLine(10, 12, 22, 12)
        painter.drawLine(10, 17, 20, 17)
        painter.drawLine(10, 22, 17, 22)
    elif kind == 1:  # timeline
        painter.drawLine(16, 5, 16, 27)
        for y in (9, 16, 23):
            painter.drawEllipse(QPointF(16, y), 2.5, 2.5)
            painter.drawLine(20, y, 25, y)
    elif kind == 2:  # portrait
        painter.drawEllipse(QRectF(12, 6, 9, 9))
        painter.drawArc(QRectF(7, 17, 20, 14), 20 * 16, 140 * 16)
    elif kind == 3:  # universe / compass
        painter.drawEllipse(QRectF(6, 6, 20, 20))
        painter.drawLine(16, 4, 16, 28)
        painter.drawLine(4, 16, 28, 16)
        painter.drawEllipse(QPointF(16, 16), 2, 2)
    elif kind == 4:  # location pin
        path = QPainterPath()
        path.moveTo(16, 28)
        path.cubicTo(8, 17, 8, 8, 16, 6)
        path.cubicTo(24, 8, 24, 17, 16, 28)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(16, 14), 3, 3)
    else:  # book outline
        painter.drawLine(16, 7, 16, 26)
        painter.drawArc(QRectF(5, 6, 12, 19), 90 * 16, 180 * 16)
        painter.drawArc(QRectF(15, 6, 12, 19), 270 * 16, 180 * 16)
        painter.drawLine(8, 26, 16, 28)
        painter.drawLine(16, 28, 24, 26)
    painter.end()
    return QIcon(pixmap)


class HeroPanel(QWidget):
    """Mountain-and-moon title panel painted by Qt at any window size."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("heroPanel")
        self.setFixedHeight(145)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(25, 16, 25, 16)
        text_column = QVBoxLayout()
        text_column.setSpacing(4)
        self.eyebrow = QLabel("RANNOVEL  /  WRITING DESK")
        self.eyebrow.setObjectName("heroEyebrow")
        self.title = QLabel("灵感摘录")
        self.title.setObjectName("heroTitle")
        self.subline = QLabel(SECTION_COPY[0][1])
        self.subline.setObjectName("heroSubline")
        text_column.addWidget(self.eyebrow)
        text_column.addWidget(self.title)
        text_column.addWidget(self.subline)
        text_column.addStretch()
        layout.addLayout(text_column, 1)
        self.badge = QLabel("✦ 只写在本地")
        self.badge.setObjectName("heroBadge")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.badge)

    def set_section(self, index: int) -> None:
        if 0 <= index < len(SECTION_COPY):
            title, subline = SECTION_COPY[index]
            self.title.setText(title)
            self.subline.setText(subline)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor("#2C4A61"))
        gradient.setColorAt(1.0, QColor("#597E8E"))
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 18, 18)
        painter.setClipRect(rect)

        width = self.width()
        height = self.height()
        moon_x = width - 178
        painter.setOpacity(0.85)
        painter.setBrush(QColor("#E7D3A9"))
        painter.drawEllipse(QRectF(moon_x, 22, 45, 45))
        painter.setOpacity(1.0)

        far = QPainterPath()
        far.moveTo(width * 0.56, height)
        far.cubicTo(width * 0.69, 69, width * 0.73, 84, width * 0.81, height)
        far.cubicTo(width * 0.89, 84, width * 0.95, 90, width, height)
        far.closeSubpath()
        painter.setBrush(QColor("#91ABB3"))
        painter.setOpacity(0.35)
        painter.drawPath(far)
        painter.setOpacity(1.0)

        near = QPainterPath()
        near.moveTo(width * 0.64, height)
        near.cubicTo(width * 0.75, 100, width * 0.79, 111, width * 0.87, height)
        near.cubicTo(width * 0.93, 107, width * 0.97, 113, width, height)
        near.closeSubpath()
        painter.setBrush(QColor("#203F54"))
        painter.setOpacity(0.45)
        painter.drawPath(near)
        painter.setOpacity(1.0)

        painter.setPen(QPen(QColor(238, 228, 198, 105), 1))
        for offset in (0, 17, 33):
            y = height - 26 + offset
            painter.drawLine(QPointF(width * 0.69, y), QPointF(width - 27, y))
        painter.end()
