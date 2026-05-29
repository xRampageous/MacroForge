"""Timeline widget for MacroForge PyQt6 (QGraphicsView-based)."""
import math
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem, QFrame
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter

from ui.theme import COLORS, TYPE_COLORS
from models import Action


class TimelineWidget(QGraphicsView):
    """Interactive timeline showing action durations, lanes, and playback position."""

    action_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._actions = []
        self._active_index = -1
        self._playing_index = -1
        self._zoom = 1.0

        self.setMinimumHeight(120)
        self.setMaximumHeight(200)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"background-color: {COLORS['bg_secondary']}; border: 1px solid {COLORS['border']}; border-radius: 8px;")

        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(0, 0, 800, 140)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        self._row_h = 28
        self._header_h = 20

        # Zoom interaction
        self._dragging = False
        self._drag_start_x = 0

    def set_actions(self, actions: list):
        self._actions = actions
        self._rebuild()

    def set_active_index(self, index: int):
        self._active_index = index
        self._rebuild()

    def set_playing(self, index: int, duration: float = 0.0):
        self._playing_index = index
        self._rebuild()

    def clear_playing(self):
        self._playing_index = -1
        self._rebuild()

    def _rebuild(self):
        self._scene.clear()
        if not self._actions:
            self._draw_empty()
            return

        w = max(self.viewport().width(), 200)
        h = len(self._actions) * self._row_h + self._header_h + 10
        self._scene.setSceneRect(0, 0, w, h)

        header = self._scene.addRect(0, 0, w, self._header_h, QPen(Qt.PenStyle.NoPen), QBrush(QColor(COLORS["bg_tertiary"])))
        header_text = self._scene.addText("Timeline", QFont("Segoe UI", 9, QFont.Weight.Bold))
        header_text.setPos(6, 0)
        header_text.setDefaultTextColor(QColor(COLORS["text_dim"]))

        for i, action in enumerate(self._actions):
            y = self._header_h + i * self._row_h
            t = getattr(action, "action_type", "key")
            color = TYPE_COLORS.get(t, COLORS["text_dim"])
            dur = getattr(action, "duration", 0.0)
            bar_w = max(4, min(w - 60, int(dur * 200 * self._zoom) + 4))

            # Row background
            bg_color = COLORS["bg_secondary"] if i % 2 == 0 else COLORS["bg"]
            if i == self._playing_index:
                bg_color = COLORS["playing_glow"]
            elif i == self._active_index:
                bg_color = COLORS["bg_hover"]
            self._scene.addRect(0, y, w, self._row_h, QPen(Qt.PenStyle.NoPen), QBrush(QColor(bg_color)))

            # Index
            idx_text = self._scene.addText(str(i + 1), QFont("Segoe UI", 8))
            idx_text.setPos(6, y + 2)
            idx_text.setDefaultTextColor(QColor(COLORS["text_dim"]))

            # Bar
            bar = self._scene.addRect(30, y + 4, bar_w, self._row_h - 10, QPen(Qt.PenStyle.NoPen), QBrush(QColor(color)))
            bar.setToolTip(f"{t}: {action.key} ({dur:.3f}s)")

            # Duration label
            dur_text = self._scene.addText(f"{dur:.3f}s", QFont("Segoe UI", 8))
            dur_text.setPos(36 + bar_w, y + 4)
            dur_text.setDefaultTextColor(QColor(COLORS["text_dim"]))

    def _draw_empty(self):
        w = max(self.viewport().width(), 200)
        text = self._scene.addText("No actions — add some to see the timeline", QFont("Segoe UI", 10))
        text.setPos(w / 2 - 140, 50)
        text.setDefaultTextColor(QColor(COLORS["text_dim"]))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            y = scene_pos.y()
            idx = int((y - self._header_h) / self._row_h)
            if 0 <= idx < len(self._actions):
                self.action_clicked.emit(idx)
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild()
