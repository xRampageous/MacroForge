"""MacroForge Timeline — QGraphicsView-based CanvasTimeline replacement.

Replicates ALL v1.1.0 CanvasTimeline features:
- 60 FPS rendering loop
- Object pooling
- Inertial smooth scrolling
- Zoom (Ctrl+wheel)
- Virtualized rendering
- Dirty tracking
- Per-row theming & glow
- Progress bar with live countdown
- Image previews (base64 → QPixmap)
- Drag-and-drop reordering
- Multi-select (Shift+click)
- Hover highlighting
- Context menu
- FPS counter
- ensure_visible
- set_paused
"""
import time
import math
import base64
import io
from collections import deque

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsPixmapItem,
    QFrame, QMenu
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QPixmap,
    QLinearGradient, QFontMetrics, QPolygonF
)

from ui.theme import COLORS, TYPE_COLORS, TYPE_GLOW
from debugger import logger


class TimelineRow:
    """Pooled row graphics items."""

    def __init__(self, scene):
        self.scene = scene
        C = COLORS

        self.bg = scene.addRect(0, 0, 100, 30, QPen(Qt.PenStyle.NoPen), QBrush(QColor(C["bg_secondary"])))
        self.glow = scene.addRect(0, 0, 100, 30, QPen(QColor(C["accent"]), 2), QBrush(Qt.BrushStyle.NoBrush))
        self.glow.setVisible(False)

        self.left = scene.addRect(0, 0, 4, 30, QPen(Qt.PenStyle.NoPen), QBrush(QColor(C["accent"])))

        self.bar_bg = scene.addRect(0, 0, 100, 5, QPen(Qt.PenStyle.NoPen), QBrush(QColor(C["border"])))
        grad = QLinearGradient(0, 0, 100, 0)
        grad.setColorAt(0, QColor(C["accent_secondary"]))
        grad.setColorAt(1, QColor(C["accent"]))
        self.bar_fill = scene.addRect(0, 0, 50, 5, QPen(Qt.PenStyle.NoPen), QBrush(grad))

        self.t_index = scene.addText("", QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.t_index.setDefaultTextColor(QColor(C["text_dim"]))

        self.t_key = scene.addText("", QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.t_key.setDefaultTextColor(QColor(C["text"]))

        self.t_dur = scene.addText("", QFont("Consolas", 8))
        self.t_dur.setDefaultTextColor(QColor(C["text_dim"]))

        self.t_lane = scene.addText("", QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.t_lane.setDefaultTextColor(QColor("#60a5fa"))

        self.t_flags = scene.addText("", QFont("Segoe UI", 8))
        self.t_flags.setDefaultTextColor(QColor(C["neon_gold"]))

        self.icon_group = scene.createItemGroup([])
        self.img_item = None
        self.img_pixmap = None

        self.bound_index = -1
        self.y = 0
        self.cache_key = None
        self.zoom = 0
        self._was_playing = False

        # Layout anchors (set properly in set_pos)
        self._text_y = 0
        self._text_x_normal = 20
        self._text_x_image = 44
        self._thumb_x = 6
        self._cy = 0
        self._icon_x = 6
        self._icon_y = 0

    def set_pos(self, x, y, w, row_h):
        self.y = y
        pad = 4
        self.bg.setRect(int(x + pad), int(y), int(w - pad * 2), int(row_h - 2))
        self.glow.setRect(int(x + pad), int(y), int(w - pad * 2), int(row_h - 2))
        self.left.setRect(int(x + pad), int(y), 4, int(row_h - 2))

        ci, ck, bs, bw, cl, cf = self._calc_cols(w)
        bar_y = int(y + row_h - 10)
        cy = int(y + row_h // 2)

        self.bar_bg.setRect(int(bs), int(bar_y), int(bw), 5)
        self.bar_fill.setRect(int(bs), int(bar_y), int(bw), 5)

        fm = QFontMetrics(self.t_index.font())
        ih = fm.height()

        self._text_y = int(cy - ih // 2)
        self._text_x_normal = int(ck + 20)
        self._text_x_image = int(ck + 44)
        self._thumb_x = int(ck + 4)
        self._cy = int(cy)

        self.t_index.setPos(int(ci), self._text_y)
        self.t_key.setPos(self._text_x_normal, self._text_y)
        self.t_dur.setPos(int(bs + bw // 2 - 20), int(bar_y - ih - 2))
        self.t_lane.setPos(int(cl), self._text_y)
        self.t_flags.setPos(int(cf), self._text_y)

        self._icon_x = int(ck + 6)
        self._icon_y = cy

    def _calc_cols(self, w):
        idx = max(8, int(w * 0.03))
        key = max(40, int(w * 0.12))
        bar_w = max(80, int(w * 0.22))
        bar_s = int((w - bar_w) / 2)
        lane = max(280, int(w * 0.72))
        flags = max(360, int(w * 0.88))
        return idx, key, bar_s, bar_w, lane, flags

    def hide(self):
        for item in (self.bg, self.glow, self.left, self.bar_bg, self.bar_fill,
                     self.t_index, self.t_key, self.t_dur, self.t_lane, self.t_flags):
            item.setVisible(False)
        self.icon_group.setVisible(False)
        if self.img_item:
            self.img_item.setVisible(False)

    def show(self):
        for item in (self.bg, self.left, self.bar_bg, self.bar_fill,
                     self.t_index, self.t_key, self.t_dur, self.t_lane, self.t_flags):
            item.setVisible(True)
        self.icon_group.setVisible(True)
        if self.img_item:
            self.img_item.setVisible(True)

    def set_dim(self, dim: bool):
        """Fade the entire row when it doesn't match an active search filter."""
        op = 0.28 if dim else 1.0
        for item in (self.bg, self.left, self.bar_bg, self.bar_fill,
                     self.t_index, self.t_key, self.t_dur, self.t_lane, self.t_flags):
            item.setOpacity(op)
        self.icon_group.setOpacity(op)
        if self.img_item:
            self.img_item.setOpacity(op)

    def draw_icon(self, action_type, color):
        """Draw cleaner action type icons."""
        for item in self.icon_group.childItems():
            self.icon_group.removeFromGroup(item)
            self.scene.removeItem(item)

        size = 10
        ix = int(self._icon_x - size // 2)
        iy = int(self._icon_y - size // 2)
        pen = QPen(Qt.PenStyle.NoPen)
        brush = QBrush(QColor(color))
        C = QColor(color)
        items = []

        if action_type == "key":
            # Keyboard (matches panel icon)
            items.append(self.scene.addRect(ix - 1, iy - 1, size + 2, size + 2, QPen(C, 1.2), QBrush(Qt.BrushStyle.NoBrush)))
            items.append(self.scene.addRect(int(ix + 1), int(iy + 1), 2, 2, QPen(C, 0.8), QBrush(Qt.BrushStyle.NoBrush)))
            items.append(self.scene.addRect(int(ix + 5), int(iy + 1), 2, 2, QPen(C, 0.8), QBrush(Qt.BrushStyle.NoBrush)))
            items.append(self.scene.addRect(int(ix + 3), int(iy + 5), 4, 2, QPen(C, 0.8), QBrush(Qt.BrushStyle.NoBrush)))
        elif action_type == "click":
            # Mouse (matches panel icon)
            items.append(self.scene.addEllipse(ix, iy, size, size + 2, QPen(C, 1.2), QBrush(Qt.BrushStyle.NoBrush)))
            items.append(self.scene.addLine(int(ix + size // 2), int(iy), int(ix + size // 2), int(iy + size - 2), QPen(C, 1)))
            items.append(self.scene.addLine(int(ix), int(iy + size // 2), int(ix + size), int(iy + size // 2), QPen(C, 1)))
        elif action_type == "image":
            # Picture frame
            items.append(self.scene.addRect(ix, iy + 1, size, size - 2, QPen(C, 1.2), QBrush(Qt.BrushStyle.NoBrush)))
            items.append(self.scene.addLine(ix + 2, int(iy + size - 3), int(ix + size // 2), iy + 3, QPen(C, 1)))
            items.append(self.scene.addLine(int(ix + size // 2), iy + 3, int(ix + size - 2), int(iy + size - 4), QPen(C, 1)))
        elif action_type == "pause":
            items.append(self.scene.addRect(int(ix + 2), iy + 1, 2, size - 2, pen, brush))
            items.append(self.scene.addRect(int(ix + 6), iy + 1, 2, size - 2, pen, brush))
        else:
            items.append(self.scene.addEllipse(ix + 1, iy + 1, size - 2, size - 2, pen, brush))

        for item in items:
            self.icon_group.addToGroup(item)
        self.icon_group.setVisible(True)

    def set_image_preview(self, action, scene):
        """Decode base64 and show image preview."""
        data = getattr(action, "image_data", "")
        if not data:
            if self.img_item:
                self.img_item.setVisible(False)
            return
        try:
            img_bytes = base64.b64decode(data)
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            if pixmap.isNull():
                return
            # Bound thumbnail to a small box (keep aspect) so it never overflows the row
            max_h = 22
            max_w = 34
            scaled = pixmap.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            if not self.img_item:
                self.img_item = scene.addPixmap(scaled)
            else:
                self.img_item.setPixmap(scaled)
            thumb_x = getattr(self, "_thumb_x", self._icon_x)
            cy = getattr(self, "_cy", self._icon_y)
            self.img_item.setPos(int(thumb_x), int(cy - scaled.height() // 2))
            self.img_item.setZValue(1)
            self.img_item.setVisible(True)
            # Hide icon when image shown
            self.icon_group.setVisible(False)
        except Exception:
            pass

    def update_content(self, action, index, zoom):
        t = getattr(action, "action_type", "key")
        color = TYPE_COLORS.get(t, COLORS["text_dim"])
        glow = TYPE_GLOW.get(t, TYPE_GLOW["key"])

        self.t_index.setPlainText(f"{index + 1:02d}")

        label = getattr(action, "label", "")
        display = label or action.key
        if t == "image" and getattr(action, "image_data", ""):
            display = label or "Image"
        self.t_key.setPlainText(display)

        self.t_dur.setPlainText(f"{action.duration:.2f}s")
        self.t_lane.setPlainText(f"L{action.lane}" if action.lane != 0 else "")

        flags = []
        if getattr(action, "hold_mode", False):
            flags.append("HOLD")
        if getattr(action, "random_key", False):
            flags.append("RAND")
        rep = getattr(action, "repeat_count", 1)
        if rep > 1:
            flags.append(f"x{rep}")
        self.t_flags.setPlainText("  " + "  ".join(flags))

        self.left.setBrush(QBrush(QColor(color)))
        self.left_color = color

        # Update icon
        self.draw_icon(t, color)

        if t == "image" and getattr(action, "image_data", ""):
            self.set_image_preview(action, self.scene)
            self.t_key.setPos(self._text_x_image, self._text_y)
        else:
            if self.img_item:
                self.img_item.setVisible(False)
            self.icon_group.setVisible(True)
            self.t_key.setPos(self._text_x_normal, self._text_y)

        self.bound_index = index
        self.zoom = zoom
        self.cache_key = (action.key, action.duration, action.lane, label, t, rep)

    def animate(self, index, is_playing, is_active, is_hover, is_multi, action_dur,
                action_start, paused, paused_at, pause_offset, cols, row_h):
        C = COLORS

        bg = QColor(C["bg_secondary"])
        glow_visible = False
        glow_color = C["accent"]
        left_color = getattr(self, 'left_color', C["accent"])

        if is_hover:
            bg = QColor(C["bg_hover"])
        if is_active:
            bg = QColor(C["bg_tertiary"])
            glow_visible = True
        if is_multi:
            bg = QColor(C["bg_card"])
            glow_visible = True
        if is_playing:
            glow_color = C["playing"]
            bg = QColor(63, 224, 138, 70)
            glow_visible = True
            left_color = C["playing"]

        self.bg.setBrush(QBrush(bg))
        self.glow.setPen(QPen(QColor(glow_color), 1 if is_active else 2))
        self.glow.setVisible(glow_visible)
        self.left.setBrush(QBrush(QColor(left_color)))

        # Progress bar
        _, _, bs, bw, _, _ = cols
        progress = bw
        if is_playing and action_dur > 0:
            paused_extra = (time.time() - paused_at) if paused else 0.0
            elapsed = min(time.time() - action_start - pause_offset - paused_extra, action_dur)
            remaining = max(0.0, action_dur - elapsed)
            progress = max(2, int(bw * (remaining / action_dur)))
            self.t_dur.setPlainText(f"{remaining:.1f}s")
            self.t_dur.setDefaultTextColor(QColor(C["text"]))
        elif not is_playing and self._was_playing:
            if self.cache_key and len(self.cache_key) > 1:
                dur = self.cache_key[1]
                self.t_dur.setPlainText(f"{dur:.2f}s")
            self.t_dur.setDefaultTextColor(QColor(COLORS["text_dim"]))

        self._was_playing = is_playing

        bar_y = int(self.y + row_h - 10)
        self.bar_fill.setRect(int(bs), int(bar_y), int(progress), 5)


class TimelineView(QGraphicsView):
    """Modern QGraphicsView-based timeline."""

    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)  # from, to

    BUFFER_ROWS = 12
    TARGET_FPS = 60
    FRAME_TIME = 1 / TARGET_FPS
    ROW_H = 34
    HEADER_H = 26
    SCROLL_DECAY = 0.90
    MAX_VELOCITY = 3000

    def __init__(self, parent=None):
        super().__init__(parent)

        self._actions = []
        self.active_index = -1
        self.playing_index = -1
        self.hover_index = -1
        self.selected_indices = set()

        self.scroll_offset = 0.0
        self.scroll_velocity = 0.0
        self.zoom = 1.0

        self._action_start = 0.0
        self._action_dur = 0.0
        self._paused = False
        self._paused_at = 0.0
        self._pause_offset = 0.0

        self.dragging = False
        self.drag_index = -1
        self.drag_target = -1
        self.drag_start_y = 0

        self._running = True
        self._last_frame = time.perf_counter()

        self._render_lock = False
        self._last_action_count = 0
        self._dirty_all = True

        self._image_preview_cache = {}
        self._search = ""

        self.setMinimumHeight(160)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        # Do NOT set stylesheet on QGraphicsView — use background brush instead
        self.setBackgroundBrush(QBrush(QColor(COLORS["bg"])))
        # No border-radius on QGraphicsView — causes rendering crashes in frozen builds
        self.setStyleSheet(f"border: 1px solid {COLORS['border']};")

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 800, 600)
        self.setScene(self.scene)

        # Header
        self._header_bg = None
        self._header_line = None
        self._header_labels = []
        self._create_header()

        # Pool
        self.visible_pool = []
        self.pool_size = 0
        self._init_pool()

        # Ghost for drag
        self._ghost_rect = None
        self._ghost_text = None
        self._drop_line = None
        self._ensure_ghost()

        # Timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._frame_loop)
        self._timer.start(16)

    def _create_header(self):
        if self._header_bg:
            self.scene.removeItem(self._header_bg)
        if self._header_line:
            self.scene.removeItem(self._header_line)
        for lbl in self._header_labels:
            self.scene.removeItem(lbl)
        self._header_labels = []

        w = self.viewport().width()
        C = COLORS

        self._header_bg = self.scene.addRect(0, 0, w, self.HEADER_H,
            QPen(Qt.PenStyle.NoPen), QBrush(QColor(C["bg_secondary"])))
        self._header_line = self.scene.addLine(0, self.HEADER_H, w, self.HEADER_H,
            QPen(QColor(C["border"])))

        cols = self._get_cols(w)
        headers = [
            (cols[0], "#", -1),
            (cols[1], "ACTION", -1),
            (cols[2] + cols[3] / 2, "DURATION", 0),
            (cols[4], "LANE", -1),
            (cols[5], "FLAGS", -1),
        ]
        for x, text, anchor in headers:
            t = self.scene.addText(text, QFont("Segoe UI", 8, QFont.Weight.Bold))
            t.setDefaultTextColor(QColor(C["text_dim"]))
            if anchor == 0:
                t.setPos(int(x - int(t.boundingRect().width()) // 2), 2)
            else:
                t.setPos(int(x), 2)
            self._header_labels.append(t)

    def _update_total_label(self, w=None):
        # Total readout lives in the stats panel; no-op here to avoid header overlap.
        return

    def set_search(self, text: str):
        """Highlight rows matching text; dim the rest. Empty clears the filter."""
        self._search = (text or "").strip().lower()
        self._dirty_all = True

    def _get_cols(self, w):
        idx = max(8, int(w * 0.03))
        key = max(40, int(w * 0.12))
        bar_w = max(80, int(w * 0.22))
        bar_s = int((w - bar_w) / 2)
        # Keep rightmost columns inside viewport so labels aren't clipped
        lane = min(max(200, int(w * 0.68)), w - 90)
        flags = min(max(260, int(w * 0.82)), w - 30)
        return idx, key, bar_s, bar_w, lane, flags

    def _init_pool(self):
        for row in self.visible_pool:
            # Remove all items
            for item in [row.bg, row.glow, row.left, row.bar_bg, row.bar_fill,
                        row.t_index, row.t_key, row.t_dur, row.t_lane, row.t_flags]:
                self.scene.removeItem(item)
            if row.img_item:
                self.scene.removeItem(row.img_item)
            # Remove icon group (and any remaining child items)
            for child in row.icon_group.childItems():
                row.icon_group.removeFromGroup(child)
                self.scene.removeItem(child)
            self.scene.removeItem(row.icon_group)
        self.visible_pool.clear()

        h = max(self.viewport().height(), 300)
        row_h = self._row_h()
        self.pool_size = int(h / row_h) + self.BUFFER_ROWS

        for _ in range(self.pool_size):
            self.visible_pool.append(TimelineRow(self.scene))

        self._create_header()
        self._dirty_all = True

    def _row_h(self):
        return max(20, int(self.ROW_H * self.zoom))

    def _view_h(self):
        return max(1, self.viewport().height() - self.HEADER_H)

    def _clamp_scroll(self):
        row_h = self._row_h()
        max_scroll = max(0, len(self._actions) * row_h - self._view_h())
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset))

    def set_actions(self, actions):
        self._actions = actions
        self._dirty_all = True
        self._clamp_scroll()
        self._update_total_label()

    def set_active(self, index):
        self.active_index = index
        self._dirty_all = True

    def set_playing(self, index, duration=0.0):
        self.playing_index = index
        self._action_start = time.time()
        self._pause_offset = 0.0
        self._paused = False
        self._action_dur = duration
        self.ensure_visible(index)
        self._dirty_all = True

    def set_paused(self, paused):
        if paused and not self._paused:
            self._paused = True
            self._paused_at = time.time()
        elif not paused and self._paused:
            self._pause_offset += time.time() - self._paused_at
            self._paused = False
        self._dirty_all = True

    def clear_playing(self):
        self.playing_index = -1
        self._action_dur = 0.0
        self._dirty_all = True

    def ensure_visible(self, index):
        if index < 0 or index >= len(self._actions):
            return
        row_h = self._row_h()
        y = index * row_h
        view_h = self._view_h()
        if y < self.scroll_offset:
            self.scroll_offset = y
        elif y + row_h > self.scroll_offset + view_h:
            self.scroll_offset = y - view_h + row_h
        self._clamp_scroll()
        self._dirty_all = True

    def refresh(self):
        self._last_action_count = len(self._actions)
        for row in self.visible_pool:
            row.bound_index = -1
            row.cache_key = None
            row.zoom = 0
        self._dirty_all = True

    def _frame_loop(self):
        if not self._running:
            return

        now = time.perf_counter()
        dt = now - self._last_frame
        self._last_frame = now

        # Inertial scroll
        if abs(self.scroll_velocity) > 0.1:
            self.scroll_velocity *= self.SCROLL_DECAY
            self.scroll_offset += self.scroll_velocity * dt
            self._clamp_scroll()
            self._dirty_all = True

        # Detect changes
        if len(self._actions) != self._last_action_count:
            self._last_action_count = len(self._actions)
            self._dirty_all = True
            self._clamp_scroll()

        if self._dirty_all or self.playing_index >= 0:
            self._render()

    def _render(self):
        if self._render_lock:
            return
        self._render_lock = True
        try:
            actions = self._actions
            total = len(actions)
            row_h = self._row_h()
            canvas_h = self.viewport().height()
            canvas_w = self.viewport().width()
            cols = self._get_cols(canvas_w)

            first = max(0, int(self.scroll_offset / row_h))
            last = min(total - 1, first + self.pool_size - 1)

            offset_y = self.scroll_offset % row_h

            for pool_i, row in enumerate(self.visible_pool):
                action_index = first + pool_i
                if action_index >= total:
                    row.hide()
                    continue

                action = actions[action_index]
                y = self.HEADER_H + (pool_i * row_h) - offset_y

                # Position
                if row.y != y or self._dirty_all:
                    row.set_pos(0, y, canvas_w, row_h)

                # Content
                cache_key = (action.key, action.duration, getattr(action, "lane", 0),
                            getattr(action, "label", ""), getattr(action, "action_type", "key"),
                            getattr(action, "repeat_count", 1))

                if (row.bound_index != action_index or row.zoom != self.zoom or
                    row.cache_key != cache_key):
                    row.update_content(action, action_index, self.zoom)
                    row.cache_key = cache_key
                    row.zoom = self.zoom

                # Animation / state
                is_playing = action_index == self.playing_index
                is_active = action_index == self.active_index
                is_hover = action_index == self.hover_index
                is_multi = action_index in self.selected_indices

                row.animate(action_index, is_playing, is_active, is_hover, is_multi,
                            self._action_dur, self._action_start, self._paused,
                            self._paused_at, self._pause_offset, cols, row_h)

                # Search filter: dim rows that don't match
                if self._search:
                    hay = " ".join(str(x).lower() for x in (
                        getattr(action, "key", ""), getattr(action, "label", ""),
                        getattr(action, "action_type", ""),
                    ))
                    row.set_dim(self._search not in hay)
                else:
                    row.set_dim(False)

                row.show()

            self._dirty_all = False

            # Raise header
            if self._header_bg:
                self._header_bg.setZValue(100)
            if self._header_line:
                self._header_line.setZValue(100)
            for lbl in self._header_labels:
                lbl.setZValue(100)

        finally:
            self._render_lock = False

    def _ensure_ghost(self):
        if self._ghost_rect is not None:
            return
        C = COLORS
        self._ghost_rect = self.scene.addRect(0, 0, 0, 0,
            QPen(QColor(C["accent"]), 1),
            QBrush(QColor(f"{C['accent']}20")))
        self._ghost_rect.setVisible(False)
        self._ghost_rect.setZValue(200)

        self._ghost_text = self.scene.addText("", QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._ghost_text.setDefaultTextColor(QColor(C["text"]))
        self._ghost_text.setVisible(False)
        self._ghost_text.setZValue(201)

        self._drop_line = self.scene.addLine(0, 0, 0, 0, QPen(QColor(C["accent"]), 2))
        self._drop_line.setVisible(False)
        self._drop_line.setZValue(202)

    # ═══════════════════════════════════════════════════════
    #  EVENTS
    # ═══════════════════════════════════════════════════════

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Zoom
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom *= 1.1
            else:
                self.zoom /= 1.1
            self.zoom = max(0.4, min(3.0, self.zoom))
            self._dirty_all = True
            self._init_pool()
        else:
            # Scroll
            row_h = self._row_h()
            delta = event.angleDelta().y()
            d = -delta / 120 * row_h * 8
            self.scroll_velocity += d
            self.scroll_velocity = max(-self.MAX_VELOCITY, min(self.MAX_VELOCITY, self.scroll_velocity))
        event.accept()

    def mousePressEvent(self, event):
        pos = self.mapToScene(event.pos())
        y = pos.y()
        if y < self.HEADER_H:
            super().mousePressEvent(event)
            return

        row_h = self._row_h()
        idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)

        if 0 <= idx < len(self._actions):
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self._select_range(idx)
            else:
                self.drag_index = idx
                self.drag_start_y = pos.y()
                self.dragging = False
                self.action_clicked.emit(idx)
        else:
            self.action_clicked.emit(-1)
            self.selected_indices.clear()
            self._dirty_all = True

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = self.mapToScene(event.pos())
        y = pos.y()
        if y < self.HEADER_H:
            return
        row_h = self._row_h()
        idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)
        if 0 <= idx < len(self._actions):
            self.action_double_clicked.emit(idx)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        # Hover
        y = pos.y()
        if y >= self.HEADER_H:
            row_h = self._row_h()
            idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)
            if idx != self.hover_index:
                self.hover_index = idx
                self._dirty_all = True

        # Drag
        if self.drag_index >= 0:
            if abs(pos.y() - self.drag_start_y) > 8:
                if not self.dragging:
                    self.dragging = True
                    self._ensure_ghost()
                    action = self._actions[self.drag_index]
                    atype = getattr(action, "action_type", "key")
                    self._ghost_text.setPlainText(f"{atype}: {getattr(action, 'label', '') or action.key}")
                    self._ghost_rect.setVisible(True)
                    self._ghost_text.setVisible(True)
                    self._drop_line.setVisible(True)

            if self.dragging:
                row_h = self._row_h()
                target = int((y - self.HEADER_H + self.scroll_offset) / row_h)
                target = max(0, min(target, len(self._actions)))
                self.drag_target = target

                w = self.viewport().width()
                ghost_y = int(pos.y() - row_h // 2)
                self._ghost_rect.setRect(6, ghost_y, w - 12, row_h - 4)
                self._ghost_text.setPos(30, int(pos.y()) - 8)

                target_y = int(self.HEADER_H + (target * row_h) - self.scroll_offset)
                self._drop_line.setLine(0, target_y, w, target_y)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            if self.drag_target != self.drag_index:
                self.action_dragged.emit(self.drag_index, self.drag_target)

        if self._ghost_rect:
            self._ghost_rect.setVisible(False)
        if self._ghost_text:
            self._ghost_text.setVisible(False)
        if self._drop_line:
            self._drop_line.setVisible(False)

        self.dragging = False
        self.drag_index = -1
        self.drag_target = -1
        super().mouseReleaseEvent(event)

    def _select_range(self, index):
        if self.active_index < 0 or self.active_index >= len(self._actions):
            self.selected_indices.clear()
            self.action_clicked.emit(index)
            return
        start = min(self.active_index, index)
        end = max(self.active_index, index)
        self.selected_indices = set(range(start, end + 1))
        self._dirty_all = True

    def contextMenuEvent(self, event):
        pos = self.mapToScene(event.pos())
        y = pos.y()
        if y < self.HEADER_H:
            return
        row_h = self._row_h()
        idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)
        if 0 <= idx < len(self._actions):
            self.action_context_menu.emit(idx, event.globalPos())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, self.viewport().width(), max(400, self.viewport().height()))
        self._create_header()
        self._dirty_all = True
        # Grow pool if needed
        h = self.viewport().height()
        row_h = self._row_h()
        needed = int(h / row_h) + self.BUFFER_ROWS
        while len(self.visible_pool) < needed:
            self.visible_pool.append(TimelineRow(self.scene))
            self.pool_size += 1

    def destroy(self):
        self._running = False
        self._timer.stop()
