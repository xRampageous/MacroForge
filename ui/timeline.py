"""MacroForge Timeline — robust QGraphicsView-based virtualized list.

Features retained:
- Virtualized rendering (only visible rows created)
- Zoom (Ctrl+wheel)
- Smooth scroll
- Progress bar with live countdown during playback
- Image previews (base64 -> QPixmap)
- Drag-and-drop reordering
- Multi-select (Shift+click)
- Hover highlighting
- Context menu
- ensure_visible
- set_paused / clear_playing
"""
import time
import base64
import io

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsPixmapItem,
    QFrame, QMenu
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QFont, QPixmap,
    QLinearGradient, QFontMetrics, QPainter
)

from ui.theme import COLORS, TYPE_COLORS, TYPE_GLOW
from debugger import logger


class TimelineRow:
    """A single visible row — created fresh each _render, destroyed when off-screen."""

    def __init__(self, scene, action, index, zoom, x, y, w, row_h, 
                 is_playing=False, is_active=False, is_hover=False, is_multi=False,
                 action_dur=0, action_start=0, paused=False, paused_at=0, pause_offset=0):
        self.scene = scene
        self.items = []
        self.img_item = None
        self._icon_items = []
        self._create(action, index, zoom, x, y, w, row_h,
                       is_playing, is_active, is_hover, is_multi,
                       action_dur, action_start, paused, paused_at, pause_offset)

    def _add(self, item):
        self.items.append(item)
        return item

    def _calc_cols(self, w):
        idx = max(8, int(w * 0.03))
        key = max(40, int(w * 0.12))
        bar_w = max(80, int(w * 0.22))
        bar_s = int((w - bar_w) / 2)
        lane = min(max(200, int(w * 0.68)), w - 90)
        flags = min(max(260, int(w * 0.82)), w - 30)
        return idx, key, bar_s, bar_w, lane, flags

    def _create(self, action, index, zoom, x, y, w, row_h, 
                is_playing, is_active, is_hover, is_multi,
                action_dur, action_start, paused, paused_at, pause_offset):
        C = COLORS
        t = getattr(action, "action_type", "key")
        color = TYPE_COLORS.get(t, C["text_dim"])
        glow_color = TYPE_GLOW.get(t, TYPE_GLOW["key"])
        pad = 4
        bx = int(x + pad)
        by = int(y)
        bw = int(w - pad * 2)
        bh = int(row_h - 2)

        # Background
        bg_color = QColor(C["bg_secondary"])
        if is_hover:
            bg_color = QColor(C["bg_hover"])
        if is_active:
            bg_color = QColor(C["bg_tertiary"])
        if is_multi:
            bg_color = QColor(C["bg_card"])
        if is_playing:
            bg_color = QColor(63, 224, 138, 70)

        self._add(self.scene.addRect(bx, by, bw, bh, QPen(Qt.PenStyle.NoPen), QBrush(bg_color)))

        # Glow border
        glow_visible = is_active or is_multi or is_playing
        if glow_visible:
            glow_c = C["playing"] if is_playing else glow_color
            self._add(self.scene.addRect(bx, by, bw, bh, QPen(QColor(glow_c), 1), QBrush(Qt.BrushStyle.NoBrush)))

        # Left accent bar
        left_c = C["playing"] if is_playing else color
        self._add(self.scene.addRect(bx, by, 4, bh, QPen(Qt.PenStyle.NoPen), QBrush(QColor(left_c))))

        # Columns
        ci, ck, bs, bar_w, cl, cf = self._calc_cols(w)
        bar_y = int(y + row_h - 10)
        cy = int(y + row_h // 2)
        fm = QFontMetrics(QFont("Segoe UI", 8, QFont.Weight.Bold))
        ih = fm.height()
        text_y = int(cy - ih // 2)

        # Progress bar background
        self._add(self.scene.addRect(int(bs), int(bar_y), int(bar_w), 5, QPen(Qt.PenStyle.NoPen), QBrush(QColor(C["border"]))))

        # Progress bar fill
        progress = bar_w
        if is_playing and action_dur > 0:
            paused_extra = (time.time() - paused_at) if paused else 0.0
            elapsed = min(time.time() - action_start - pause_offset - paused_extra, action_dur)
            remaining = max(0.0, action_dur - elapsed)
            progress = max(2, int(bar_w * (remaining / action_dur)))
            dur_text = f"{remaining:.1f}s"
            dur_color = QColor(C["text"])
        else:
            dur_text = f"{action.duration:.2f}s"
            dur_color = QColor(C["text_dim"])

        grad = QLinearGradient(0, 0, bar_w, 0)
        grad.setColorAt(0, QColor(C["accent_secondary"]))
        grad.setColorAt(1, QColor(C["accent"]))
        self._add(self.scene.addRect(int(bs), int(bar_y), int(progress), 5, QPen(Qt.PenStyle.NoPen), QBrush(grad)))

        # Index
        ti = self._add(self.scene.addText(f"{index + 1:02d}", QFont("Segoe UI", 8, QFont.Weight.Bold)))
        ti.setDefaultTextColor(QColor(C["text_dim"]))
        ti.setPos(int(ci), text_y)

        # Key / label
        label = getattr(action, "label", "")
        display = label or action.key
        if t == "image" and getattr(action, "image_data", ""):
            display = label or "Image"

        tk = self._add(self.scene.addText(display, QFont("Segoe UI", 10, QFont.Weight.Bold)))
        tk.setDefaultTextColor(QColor(C["text"]))

        # Duration
        td = self._add(self.scene.addText(dur_text, QFont("Consolas", 8)))
        td.setDefaultTextColor(dur_color)
        td.setPos(int(bs + bar_w // 2 - 20), int(bar_y - ih - 2))

        # Lane
        tl = self._add(self.scene.addText(f"L{action.lane}" if action.lane != 0 else "", QFont("Segoe UI", 8, QFont.Weight.Bold)))
        tl.setDefaultTextColor(QColor("#60a5fa"))
        tl.setPos(int(cl), text_y)

        # Flags
        flags = []
        if getattr(action, "hold_mode", False):
            flags.append("HOLD")
        if getattr(action, "random_key", False):
            flags.append("RAND")
        rep = getattr(action, "repeat_count", 1)
        if rep > 1:
            flags.append(f"x{rep}")
        tf = self._add(self.scene.addText("  " + "  ".join(flags), QFont("Segoe UI", 8)))
        tf.setDefaultTextColor(QColor(C["neon_gold"]))
        tf.setPos(int(cf), text_y)

        # Icon or image preview
        thumb_x = int(ck + 4)
        text_x = int(ck + 20)
        has_image = t == "image" and getattr(action, "image_data", "")

        if has_image:
            self._draw_image_preview(action, thumb_x, cy)
            text_x = int(ck + 44)
        else:
            self._draw_icon(t, color, int(ck + 6), cy)

        tk.setPos(text_x, text_y)

    def _draw_icon(self, action_type, color, cx, cy):
        size = 10
        ix = int(cx - size // 2)
        iy = int(cy - size // 2)
        C = QColor(color)
        pen = QPen(C, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        if action_type == "key":
            self._icon_items.append(self.scene.addRect(ix - 1, iy - 1, size + 2, size + 2, QPen(C, 1.2), QBrush(Qt.BrushStyle.NoBrush)))
            self._icon_items.append(self.scene.addRect(int(ix + 1), int(iy + 1), 2, 2, QPen(C, 0.8), QBrush(Qt.BrushStyle.NoBrush)))
            self._icon_items.append(self.scene.addRect(int(ix + 5), int(iy + 1), 2, 2, QPen(C, 0.8), QBrush(Qt.BrushStyle.NoBrush)))
            self._icon_items.append(self.scene.addRect(int(ix + 3), int(iy + 5), 4, 2, QPen(C, 0.8), QBrush(Qt.BrushStyle.NoBrush)))
        elif action_type == "click":
            self._icon_items.append(self.scene.addEllipse(ix, iy, size, size + 2, QPen(C, 1.2), QBrush(Qt.BrushStyle.NoBrush)))
            self._icon_items.append(self.scene.addLine(int(ix + size // 2), int(iy), int(ix + size // 2), int(iy + size - 2), QPen(C, 1)))
            self._icon_items.append(self.scene.addLine(int(ix), int(iy + size // 2), int(ix + size), int(iy + size // 2), QPen(C, 1)))
        elif action_type == "image":
            self._icon_items.append(self.scene.addRect(ix, iy + 1, size, size - 2, QPen(C, 1.2), QBrush(Qt.BrushStyle.NoBrush)))
            self._icon_items.append(self.scene.addLine(ix + 2, int(iy + size - 3), int(ix + size // 2), iy + 3, QPen(C, 1)))
            self._icon_items.append(self.scene.addLine(int(ix + size // 2), iy + 3, int(ix + size - 2), int(iy + size - 4), QPen(C, 1)))
        elif action_type == "pause":
            self._icon_items.append(self.scene.addRect(int(ix + 2), iy + 1, 2, size - 2, QPen(Qt.PenStyle.NoPen), QBrush(QColor(color))))
            self._icon_items.append(self.scene.addRect(int(ix + 6), iy + 1, 2, size - 2, QPen(Qt.PenStyle.NoPen), QBrush(QColor(color))))
        else:
            self._icon_items.append(self.scene.addEllipse(ix + 1, iy + 1, size - 2, size - 2, QPen(Qt.PenStyle.NoPen), QBrush(QColor(color))))

        for item in self._icon_items:
            self.items.append(item)

    def _draw_image_preview(self, action, thumb_x, cy):
        data = getattr(action, "image_data", "")
        if not data:
            return
        try:
            img_bytes = base64.b64decode(data)
            pixmap = QPixmap()
            pixmap.loadFromData(img_bytes)
            if pixmap.isNull():
                return
            max_h = 22
            max_w = 34
            scaled = pixmap.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.img_item = self.scene.addPixmap(scaled)
            self.img_item.setPos(int(thumb_x), int(cy - scaled.height() // 2))
            self.img_item.setZValue(1)
            self.items.append(self.img_item)
        except Exception:
            pass

    def destroy(self):
        for item in self.items:
            self.scene.removeItem(item)
        self.items.clear()
        self._icon_items.clear()
        self.img_item = None


class TimelineView(QGraphicsView):
    """Modern QGraphicsView-based timeline — recreate visible rows on every render."""

    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)

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
        self._search = ""
        self._visible_rows = []

        self.setMinimumHeight(160)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor(COLORS["bg"])))
        self.setStyleSheet(f"border: 1px solid {COLORS['border']};")

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 800, 600)
        self.setScene(self.scene)

        self._header_bg = None
        self._header_line = None
        self._header_labels = []
        self._create_header()

        self._ghost_rect = None
        self._ghost_text = None
        self._drop_line = None
        self._ensure_ghost()

        # Playback timer only — rendering is done on-demand
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_playback_tick)
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

    def _get_cols(self, w):
        idx = max(8, int(w * 0.03))
        key = max(40, int(w * 0.12))
        bar_w = max(80, int(w * 0.22))
        bar_s = int((w - bar_w) / 2)
        lane = min(max(200, int(w * 0.68)), w - 90)
        flags = min(max(260, int(w * 0.82)), w - 30)
        return idx, key, bar_s, bar_w, lane, flags

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
        self._clamp_scroll()
        self._render()

    def set_active(self, index):
        self.active_index = index
        self._render()

    def set_playing(self, index, duration=0.0):
        self.playing_index = index
        self._action_start = time.time()
        self._pause_offset = 0.0
        self._paused = False
        self._action_dur = duration
        self.ensure_visible(index)
        self._render()

    def set_paused(self, paused):
        if paused and not self._paused:
            self._paused = True
            self._paused_at = time.time()
        elif not paused and self._paused:
            self._pause_offset += time.time() - self._paused_at
            self._paused = False
        self._render()

    def clear_playing(self):
        self.playing_index = -1
        self._action_dur = 0.0
        self._render()

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
        self._render()

    def refresh(self):
        self._render()

    def set_search(self, text: str):
        self._search = (text or "").strip().lower()
        self._render()

    def _render(self):
        try:
            # Destroy old visible rows
            for row in self._visible_rows:
                row.destroy()
            self._visible_rows.clear()

            total = len(self._actions)
            if total == 0:
                self._create_header()
                return

            row_h = self._row_h()
            canvas_w = self.viewport().width()
            canvas_h = self.viewport().height()

            first = max(0, int(self.scroll_offset / row_h))
            last = min(total - 1, first + int(canvas_h / row_h) + 2)
            offset_y = self.scroll_offset % row_h

            for i in range(first, last + 1):
                action = self._actions[i]
                y = self.HEADER_H + ((i - first) * row_h) - offset_y
                is_playing = i == self.playing_index
                is_active = i == self.active_index
                is_hover = i == self.hover_index
                is_multi = i in self.selected_indices

                row = TimelineRow(
                    self.scene, action, i, self.zoom, 0, y, canvas_w, row_h,
                    is_playing, is_active, is_hover, is_multi,
                    self._action_dur, self._action_start, self._paused,
                    self._paused_at, self._pause_offset
                )
                self._visible_rows.append(row)

                # Search dim
                if self._search:
                    hay = " ".join(str(x).lower() for x in (
                        getattr(action, "key", ""), getattr(action, "label", ""),
                        getattr(action, "action_type", ""),
                    ))
                    if self._search not in hay:
                        for item in row.items:
                            item.setOpacity(0.28)

            self._create_header()
            self._raise_header()
        except Exception as e:
            logger.error(f"Timeline _render: {e}")

    def _raise_header(self):
        if self._header_bg:
            self._header_bg.setZValue(100)
        if self._header_line:
            self._header_line.setZValue(100)
        for lbl in self._header_labels:
            lbl.setZValue(100)

    def _on_playback_tick(self):
        if self.playing_index >= 0:
            self._render()

    # ═══════════════════════════════════════════════════════
    #  EVENTS
    # ═══════════════════════════════════════════════════════

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom *= 1.1
            else:
                self.zoom /= 1.1
            self.zoom = max(0.4, min(3.0, self.zoom))
            self._clamp_scroll()
            self._render()
        else:
            row_h = self._row_h()
            delta = event.angleDelta().y()
            d = -delta / 120 * row_h * 8
            self.scroll_velocity += d
            self.scroll_velocity = max(-self.MAX_VELOCITY, min(self.MAX_VELOCITY, self.scroll_velocity))
            self._start_inertial_scroll()
        event.accept()

    def _start_inertial_scroll(self):
        if hasattr(self, '_scroll_timer') and self._scroll_timer and self._scroll_timer.isActive():
            return
        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._inertial_tick)
        self._scroll_timer.start(16)

    def _inertial_tick(self):
        if abs(self.scroll_velocity) > 0.1:
            self.scroll_velocity *= self.SCROLL_DECAY
            self.scroll_offset += self.scroll_velocity * 0.016
            self._clamp_scroll()
            self._render()
        else:
            self.scroll_velocity = 0.0
            if hasattr(self, '_scroll_timer') and self._scroll_timer:
                self._scroll_timer.stop()
                self._scroll_timer = None

    def mousePressEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
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
            self._render()

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        y = pos.y()
        if y < self.HEADER_H:
            return
        row_h = self._row_h()
        idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)
        if 0 <= idx < len(self._actions):
            self.action_double_clicked.emit(idx)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        y = pos.y()
        if y >= self.HEADER_H:
            row_h = self._row_h()
            idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)
            if idx != self.hover_index:
                self.hover_index = idx
                self._render()

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
        self._render()

    def contextMenuEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        y = pos.y()
        if y < self.HEADER_H:
            return
        row_h = self._row_h()
        idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)
        if 0 <= idx < len(self._actions):
            self.action_context_menu.emit(idx, event.globalPosition().toPoint())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, self.viewport().width(), max(400, self.viewport().height()))
        self._render()

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

    def destroy(self):
        self._running = False
        self._timer.stop()
        for row in self._visible_rows:
            row.destroy()
        self._visible_rows.clear()
