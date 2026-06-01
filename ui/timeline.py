"""MacroForge Timeline — robust, smooth, feature-rich QGraphicsView-based action list."""
import time, base64
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsPixmapItem,
    QGraphicsItemGroup, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QFontMetrics, QPixmap, QLinearGradient, QPainter
from ui.theme import COLORS, TYPE_COLORS, TYPE_GLOW
from debugger import logger

class _PoolRow(QGraphicsItemGroup):
    def __init__(self, scene):
        super().__init__()
        self._scene = scene
        scene.addItem(self)
        self.setZValue(1)
        self._build()
        self._bound_idx = -1
        self._cache_key = None
        self.hide()

    def _build(self):
        self._bg = QGraphicsRectItem(self)
        self._glow = QGraphicsRectItem(self)
        self._accent = QGraphicsRectItem(self)
        self._prog_bg = QGraphicsRectItem(self)
        self._prog_fill = QGraphicsRectItem(self)
        self._idx_txt = QGraphicsTextItem(self)
        self._icon_grp = QGraphicsItemGroup(self)
        self._img_item = None
        self._label = QGraphicsTextItem(self)
        self._dur = QGraphicsTextItem(self)
        self._lane = QGraphicsTextItem(self)
        self._flags = QGraphicsTextItem(self)

    def _cols(self, w):
        return max(8, int(w * 0.03)), max(40, int(w * 0.12)), max(80, int(w * 0.22)), int((w - max(80, int(w * 0.22))) / 2), min(max(200, int(w * 0.68)), w - 90), min(max(260, int(w * 0.82)), w - 30)

    def update_content(self, action, index, zoom, w, row_h):
        t = getattr(action, "action_type", "key")
        color = TYPE_COLORS.get(t, COLORS["text_dim"])
        pad = 4
        bx, by, bw, bh = pad, 0, w - pad * 2, row_h - 2
        ci, ck, bar_w, bs, cl, cf = self._cols(w)
        bar_y = int(row_h - 10)
        cy = int(row_h // 2)
        fm = QFontMetrics(QFont("Segoe UI", 8, QFont.Weight.Bold))
        ih = fm.height()
        text_y = int(cy - ih // 2)

        self._bg.setRect(bx, by, bw, bh)
        self._bg.setPen(QPen(Qt.PenStyle.NoPen))
        self._bg.setBrush(QBrush(QColor(COLORS["bg_secondary"])))
        self._glow.setRect(bx, by, bw, bh)
        self._glow.setPen(QPen(Qt.PenStyle.NoPen))
        self._glow.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self._accent.setRect(bx, by, 4, bh)
        self._accent.setPen(QPen(Qt.PenStyle.NoPen))
        self._accent.setBrush(QBrush(QColor(color)))

        self._prog_bg.setRect(int(bs), int(bar_y), int(bar_w), 5)
        self._prog_bg.setPen(QPen(Qt.PenStyle.NoPen))
        self._prog_bg.setBrush(QBrush(QColor(COLORS["border"])))
        self._prog_fill.setRect(int(bs), int(bar_y), int(bar_w), 5)
        self._prog_fill.setPen(QPen(Qt.PenStyle.NoPen))
        grad = QLinearGradient(0, 0, bar_w, 0)
        grad.setColorAt(0, QColor(COLORS["accent_secondary"]))
        grad.setColorAt(1, QColor(COLORS["accent"]))
        self._prog_fill.setBrush(QBrush(grad))

        self._idx_txt.setPlainText(f"{index + 1:02d}")
        self._idx_txt.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._idx_txt.setDefaultTextColor(QColor(COLORS["text_dim"]))
        self._idx_txt.setPos(int(ci), text_y)

        for child in list(self._icon_grp.childItems()):
            if child.scene():
                self._scene.removeItem(child)
        if self._img_item and self._img_item.scene():
            self._scene.removeItem(self._img_item)
            self._img_item = None

        has_image = t == "image" and getattr(action, "image_data", "")
        thumb_x = int(ck + 4)
        text_x = int(ck + 20)
        if has_image:
            self._draw_image(action, thumb_x, cy)
            text_x = int(ck + 44)
        else:
            self._draw_icon(t, color, int(ck + 6), cy)

        label = getattr(action, "label", "")
        display = label or action.key
        if t == "image" and getattr(action, "image_data", ""):
            display = label or "Image"
        self._label.setPlainText(display)
        self._label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._label.setDefaultTextColor(QColor(COLORS["text"]))
        self._label.setPos(text_x, text_y)

        self._dur.setFont(QFont("Consolas", 8))
        self._dur.setPos(int(bs + bar_w // 2 - 20), int(bar_y - ih - 2))

        lane_txt = f"L{action.lane}" if action.lane != 0 else ""
        self._lane.setPlainText(lane_txt)
        self._lane.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._lane.setDefaultTextColor(QColor("#60a5fa"))
        self._lane.setPos(int(cl), text_y)

        flags = []
        if getattr(action, "hold_mode", False): flags.append("HOLD")
        if getattr(action, "random_key", False): flags.append("RAND")
        rep = getattr(action, "repeat_count", 1)
        if rep > 1: flags.append(f"x{rep}")
        self._flags.setPlainText("  " + "  ".join(flags))
        self._flags.setFont(QFont("Segoe UI", 8))
        self._flags.setDefaultTextColor(QColor(COLORS["neon_gold"]))
        self._flags.setPos(int(cf), text_y)

        self._bound_idx = index
        self._cache_key = (action.key, action.duration, action.lane, label, t, rep)
        self._action_type = t

    def _draw_icon(self, action_type, color, cx, cy):
        size, ix, iy = 10, int(cx - 5), int(cy - 5)
        C = QColor(color)
        items = []
        if action_type == "key":
            items = [QGraphicsRectItem(ix - 1, iy - 1, size + 2, size + 2),
                     QGraphicsRectItem(ix + 1, iy + 1, 2, 2),
                     QGraphicsRectItem(ix + 5, iy + 1, 2, 2),
                     QGraphicsRectItem(ix + 3, iy + 5, 4, 2)]
            items[0].setPen(QPen(C, 1.2)); items[0].setBrush(QBrush(Qt.BrushStyle.NoBrush))
            for i in items[1:]: i.setPen(QPen(C, 0.8)); i.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        elif action_type == "click":
            items = [QGraphicsRectItem(ix, iy, size, size + 2)]
            items[0].setPen(QPen(C, 1.2)); items[0].setBrush(QBrush(Qt.BrushStyle.NoBrush))
            items += [self._scene.addLine(int(ix + size // 2), iy, int(ix + size // 2), iy + size - 2, QPen(C, 1)),
                      self._scene.addLine(ix, int(iy + size // 2), ix + size, int(iy + size // 2), QPen(C, 1))]
        elif action_type == "image":
            items = [QGraphicsRectItem(ix, iy + 1, size, size - 2)]
            items[0].setPen(QPen(C, 1.2)); items[0].setBrush(QBrush(Qt.BrushStyle.NoBrush))
            items += [self._scene.addLine(ix + 2, int(iy + size - 3), int(ix + size // 2), iy + 3, QPen(C, 1)),
                      self._scene.addLine(int(ix + size // 2), iy + 3, int(ix + size - 2), int(iy + size - 4), QPen(C, 1))]
        elif action_type == "pause":
            items = [QGraphicsRectItem(ix + 2, iy + 1, 2, size - 2), QGraphicsRectItem(ix + 6, iy + 1, 2, size - 2)]
            for i in items: i.setPen(QPen(Qt.PenStyle.NoPen)); i.setBrush(QBrush(QColor(color)))
        else:
            items = [QGraphicsRectItem(ix + 1, iy + 1, size - 2, size - 2)]
            items[0].setPen(QPen(Qt.PenStyle.NoPen)); items[0].setBrush(QBrush(QColor(color)))
        for it in items:
            if it.scene() is None: self._scene.addItem(it)
            self._icon_grp.addToGroup(it)

    def _draw_image(self, action, thumb_x, cy):
        data = getattr(action, "image_data", "")
        if not data: return
        try:
            img_bytes = base64.b64decode(data)
            pixmap = QPixmap(); pixmap.loadFromData(img_bytes)
            if pixmap.isNull(): return
            scaled = pixmap.scaled(34, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._img_item = QGraphicsPixmapItem(scaled)
            self._img_item.setPos(int(thumb_x), int(cy - scaled.height() // 2))
            self._img_item.setZValue(2)
            self._icon_grp.addToGroup(self._img_item)
        except Exception: pass

    def animate(self, is_playing, is_active, is_hover, is_multi, action_dur, action_start, paused, paused_at, pause_offset, w, row_h):
        C = COLORS
        t = getattr(self, "_action_type", "key")
        if is_playing:
            bg = QColor(63, 224, 138, 180)
            glow_c = C["playing"]
            accent_c = QColor(63, 224, 138)
            label_c = QColor("#ffffff")
            idx_c = QColor("#c8f7dc")
        elif is_active:
            bg = QColor(C["bg_tertiary"])
            glow_c = TYPE_GLOW.get(t, TYPE_GLOW["key"])
            accent_c = TYPE_COLORS.get(t, C["text_dim"])
            label_c = QColor(C["text"])
            idx_c = QColor(C["text_dim"])
        elif is_multi:
            bg = QColor(C["bg_card"])
            glow_c = TYPE_GLOW.get(t, TYPE_GLOW["key"])
            accent_c = TYPE_COLORS.get(t, C["text_dim"])
            label_c = QColor(C["text"])
            idx_c = QColor(C["text_dim"])
        elif is_hover:
            bg = QColor(C["bg_hover"])
            glow_c = None
            accent_c = TYPE_COLORS.get(t, C["text_dim"])
            label_c = QColor(C["text"])
            idx_c = QColor(C["text_dim"])
        else:
            bg = QColor(C["bg_secondary"])
            glow_c = None
            accent_c = TYPE_COLORS.get(t, C["text_dim"])
            label_c = QColor(C["text"])
            idx_c = QColor(C["text_dim"])

        self._bg.setBrush(QBrush(bg))
        self._accent.setBrush(QBrush(QColor(accent_c)))
        self._label.setDefaultTextColor(QColor(label_c))
        self._idx_txt.setDefaultTextColor(QColor(idx_c))

        if glow_c:
            self._glow.setPen(QPen(QColor(glow_c), 2))
            self._glow.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        else:
            self._glow.setPen(QPen(Qt.PenStyle.NoPen))
            self._glow.setBrush(QBrush(Qt.BrushStyle.NoBrush))

        _, _, bar_w, bs, _, _ = self._cols(w)
        if is_playing and action_dur > 0:
            paused_extra = (time.time() - paused_at) if paused else 0.0
            elapsed = min(time.time() - action_start - pause_offset - paused_extra, action_dur)
            remaining = max(0.0, action_dur - elapsed)
            progress = max(2, int(bar_w * (remaining / action_dur)))
            dur_text = f"{remaining:.1f}s"
            dur_color = QColor("#ffffff")
        else:
            progress = bar_w
            dur_text = f"{action_dur:.2f}s" if action_dur > 0 else "0.00s"
            dur_color = QColor(C["text_dim"])
        self._prog_fill.setRect(int(bs), int(self._prog_fill.rect().y()), int(progress), 5)
        self._dur.setPlainText(dur_text)
        self._dur.setDefaultTextColor(dur_color)

    def apply_search_dim(self, dim):
        self.setOpacity(0.28 if dim else 1.0)

    def prepare_for_reuse(self):
        self.hide()
        self._bound_idx = -1
        self._cache_key = None
        if self._img_item and self._img_item.scene():
            self._scene.removeItem(self._img_item)
            self._img_item = None


class TimelineView(QGraphicsView):
    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)

    ROW_H = 34
    HEADER_H = 26
    SCROLL_DECAY = 0.88
    MAX_VELOCITY = 4000

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
        self._search = ""
        self._running = True
        self._needs_layout = True

        self.dragging = False
        self.drag_index = -1
        self.drag_target = -1
        self.drag_start_y = 0

        self.setMinimumHeight(160)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor(COLORS["bg"])))
        self.setStyleSheet(f"border: 1px solid {COLORS['border']};")

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, 800, 600)
        self.setScene(self.scene)

        self._header_bg = None
        self._header_line = None
        self._header_labels = []
        self._create_header()

        self._pool = []
        self._active_rows = {}
        self._scroll_timer = None

        self._ghost_rect = None
        self._ghost_text = None
        self._drop_line = None
        self._ensure_ghost()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _get_cols(self, w):
        return max(8, int(w * 0.03)), max(40, int(w * 0.12)), max(80, int(w * 0.22)), int((w - max(80, int(w * 0.22))) / 2), min(max(200, int(w * 0.68)), w - 90), min(max(260, int(w * 0.82)), w - 30)

    def _row_h(self):
        return max(20, int(self.ROW_H * self.zoom))

    def _view_h(self):
        return max(1, self.viewport().height() - self.HEADER_H)

    def _clamp_scroll(self):
        row_h = self._row_h()
        max_scroll = max(0, len(self._actions) * row_h - self._view_h())
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset))

    def _create_header(self):
        if self._header_bg: self.scene.removeItem(self._header_bg)
        if self._header_line: self.scene.removeItem(self._header_line)
        for lbl in self._header_labels: self.scene.removeItem(lbl)
        self._header_labels = []
        w = self.viewport().width()
        C = COLORS
        self._header_bg = self.scene.addRect(0, 0, w, self.HEADER_H, QPen(Qt.PenStyle.NoPen), QBrush(QColor(C["bg_secondary"])))
        self._header_line = self.scene.addLine(0, self.HEADER_H, w, self.HEADER_H, QPen(QColor(C["border"])))
        cols = self._get_cols(w)
        headers = [(cols[0], "#", -1), (cols[1], "ACTION", -1), (cols[2] + cols[3] / 2, "DURATION", 0), (cols[4], "LANE", -1), (cols[5], "FLAGS", -1)]
        for x, text, anchor in headers:
            t = self.scene.addText(text, QFont("Segoe UI", 8, QFont.Weight.Bold))
            t.setDefaultTextColor(QColor(C["text_dim"]))
            t.setPos(int(x - int(t.boundingRect().width()) // 2) if anchor == 0 else int(x), 2)
            self._header_labels.append(t)
        self._raise_header()

    def _raise_header(self):
        for item in [self._header_bg, self._header_line] + self._header_labels:
            if item: item.setZValue(100)

    def _acquire_row(self):
        for row in self._pool:
            if row._bound_idx == -1:
                return row
        row = _PoolRow(self.scene)
        self._pool.append(row)
        return row

    def _release_row(self, row):
        row.prepare_for_reuse()

    def _tick(self):
        if not self._running: return
        try:
            if abs(self.scroll_velocity) > 0.5:
                self.scroll_velocity *= self.SCROLL_DECAY
                self.scroll_offset += self.scroll_velocity * 0.016
                self._clamp_scroll()
                self._needs_layout = True
            else:
                self.scroll_velocity = 0.0
                if self._scroll_timer:
                    self._scroll_timer.stop()
                    self._scroll_timer = None
            if self.playing_index >= 0:
                self._needs_layout = True
            if self._needs_layout:
                self._layout_rows()
                self._needs_layout = False
        except Exception as e:
            logger.error(f"Timeline _tick: {e}")

    def _layout_rows(self):
        total = len(self._actions)
        if total == 0:
            self._create_header()
            for row in list(self._active_rows.values()): self._release_row(row)
            self._active_rows.clear()
            return
        row_h = self._row_h()
        canvas_w = self.viewport().width()
        canvas_h = self.viewport().height()
        first = max(0, int(self.scroll_offset / row_h))
        last = min(total - 1, first + int(canvas_h / row_h) + 2)
        offset_y = self.scroll_offset % row_h

        for idx in list(self._active_rows.keys()):
            if idx < first or idx > last:
                self._release_row(self._active_rows[idx])
                del self._active_rows[idx]

        for i in range(first, last + 1):
            action = self._actions[i]
            y = self.HEADER_H + ((i - first) * row_h) - offset_y
            is_playing = i == self.playing_index
            is_active = i == self.active_index
            is_hover = i == self.hover_index
            is_multi = i in self.selected_indices

            if i in self._active_rows:
                row = self._active_rows[i]
            else:
                row = self._acquire_row()
                self._active_rows[i] = row
                row.update_content(action, i, self.zoom, canvas_w, row_h)
                row.show()

            row.setPos(0, int(y))
            row.animate(is_playing, is_active, is_hover, is_multi, self._action_dur, self._action_start, self._paused, self._paused_at, self._pause_offset, canvas_w, row_h)

            if not is_playing:
                row._dur.setPlainText(f"{action.duration:.2f}s")
                row._dur.setDefaultTextColor(QColor(COLORS["text_dim"]))

            if self._search:
                hay = " ".join(str(x).lower() for x in (getattr(action, "key", ""), getattr(action, "label", ""), getattr(action, "action_type", "")))
                row.apply_search_dim(self._search not in hay)
            else:
                row.apply_search_dim(False)

        self._create_header()
        if self.playing_index >= 0:
            self.viewport().update()

    def set_actions(self, actions):
        self._actions = actions
        for row in list(self._active_rows.values()): self._release_row(row)
        self._active_rows.clear()
        self._clamp_scroll()
        self._needs_layout = True

    def set_active(self, index):
        self.active_index = index
        self._needs_layout = True

    def set_playing(self, index, duration=0.0):
        self.playing_index = index
        self._action_start = time.time()
        self._pause_offset = 0.0
        self._paused = False
        self._action_dur = duration
        self.ensure_visible(index)
        self._needs_layout = True

    def set_paused(self, paused):
        if paused and not self._paused:
            self._paused = True
            self._paused_at = time.time()
        elif not paused and self._paused:
            self._pause_offset += time.time() - self._paused_at
            self._paused = False
        self._needs_layout = True

    def clear_playing(self):
        self.playing_index = -1
        self._action_dur = 0.0
        self._needs_layout = True

    def ensure_visible(self, index):
        if index < 0 or index >= len(self._actions): return
        row_h = self._row_h()
        y = index * row_h
        view_h = self._view_h()
        changed = False
        if y < self.scroll_offset: self.scroll_offset = y; changed = True
        elif y + row_h > self.scroll_offset + view_h: self.scroll_offset = y - view_h + row_h; changed = True
        if changed:
            self._clamp_scroll()
            self._needs_layout = True

    def refresh(self):
        self._needs_layout = True

    def set_search(self, text: str):
        self._search = (text or "").strip().lower()
        self._needs_layout = True

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            self.zoom *= 1.1 if delta > 0 else (1 / 1.1)
            self.zoom = max(0.4, min(3.0, self.zoom))
            self._clamp_scroll()
            self._needs_layout = True
        else:
            row_h = self._row_h()
            delta = event.angleDelta().y()
            self.scroll_velocity += -delta / 120 * row_h * 8
            self.scroll_velocity = max(-self.MAX_VELOCITY, min(self.MAX_VELOCITY, self.scroll_velocity))
            if not self._scroll_timer:
                self._scroll_timer = QTimer(self)
                self._scroll_timer.timeout.connect(self._tick)
            if not self._scroll_timer.isActive():
                self._scroll_timer.start(16)
        event.accept()

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
            self._needs_layout = True
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        y = pos.y()
        if y < self.HEADER_H: return
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
                self._needs_layout = True
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
        if self.dragging and self.drag_target != self.drag_index:
            self.action_dragged.emit(self.drag_index, self.drag_target)
        if self._ghost_rect: self._ghost_rect.setVisible(False)
        if self._ghost_text: self._ghost_text.setVisible(False)
        if self._drop_line: self._drop_line.setVisible(False)
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
        self._needs_layout = True

    def contextMenuEvent(self, event):
        pos = self.mapToScene(event.position().toPoint())
        y = pos.y()
        if y < self.HEADER_H: return
        row_h = self._row_h()
        idx = int((y - self.HEADER_H + self.scroll_offset) / row_h)
        if 0 <= idx < len(self._actions):
            self.action_context_menu.emit(idx, event.globalPosition().toPoint())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, self.viewport().width(), max(400, self.viewport().height()))
        self._needs_layout = True

    def _ensure_ghost(self):
        if self._ghost_rect is not None: return
        C = COLORS
        self._ghost_rect = self.scene.addRect(0, 0, 0, 0, QPen(QColor(C["accent"]), 1), QBrush(QColor(f"{C['accent']}20")))
        self._ghost_rect.setVisible(False); self._ghost_rect.setZValue(200)
        self._ghost_text = self.scene.addText("", QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._ghost_text.setDefaultTextColor(QColor(C["text"])); self._ghost_text.setVisible(False); self._ghost_text.setZValue(201)
        self._drop_line = self.scene.addLine(0, 0, 0, 0, QPen(QColor(C["accent"]), 2))
        self._drop_line.setVisible(False); self._drop_line.setZValue(202)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Down:
            if self.active_index + 1 < len(self._actions):
                self.action_clicked.emit(self.active_index + 1)
                self.ensure_visible(self.active_index + 1)
        elif event.key() == Qt.Key.Key_Up:
            if self.active_index > 0:
                self.action_clicked.emit(self.active_index - 1)
                self.ensure_visible(self.active_index - 1)
        else:
            super().keyPressEvent(event)

    def destroy(self):
        self._running = False
        self._timer.stop()
        if self._scroll_timer:
            self._scroll_timer.stop()
        for row in list(self._active_rows.values()): self._release_row(row)
        self._active_rows.clear()
