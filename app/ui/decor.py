"""Tiny code-native ornaments; no external assets or network needed."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


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
        self.subline = QLabel("先收下句子，再让它找到自己的故事。")
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
