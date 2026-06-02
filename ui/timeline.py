"""MacroForge Timeline — high-performance polished action list.

This QListView timeline keeps the public API used by main_window.py while
rendering a modern, information-rich action row using one lightweight delegate.
It intentionally avoids widgets-per-row so large macros remain fast.
"""

import time
from PyQt6.QtWidgets import QStyledItemDelegate, QListView, QAbstractItemView, QStyle
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QSize, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPainterPath, QLinearGradient

from ui.theme import COLORS, TYPE_COLORS
from models import ActionListModel


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(value)))


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    """Blend two #RRGGBB colours."""
    t = _clamp(t)
    a = QColor(hex_a)
    b = QColor(hex_b)
    r = int(a.red() + (b.red() - a.red()) * t)
    g = int(a.green() + (b.green() - a.green()) * t)
    bl = int(a.blue() + (b.blue() - a.blue()) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def _action_kind(action) -> str:
    if not action:
        return "key"
    if getattr(action, "action_type", "key") == "pause" or getattr(action, "key", "") in ("[PAUSE]", "[DELAY]"):
        return "pause"
    return getattr(action, "action_type", "key") or "key"


def _duration_text(action) -> str:
    if not action:
        return ""
    kind = _action_kind(action)
    dur = float(getattr(action, "duration", 0.0) or 0.0)
    if kind == "pause":
        return f"{dur:.2f}s"
    if kind == "image":
        timeout = float(getattr(action, "wait_timeout", 0.0) or 0.0)
        return f"≤ {timeout:.1f}s" if timeout > 0 else "~250ms"
    if kind == "click":
        return f"{dur:.2f}s" if dur >= 0.05 else "< 50ms"
    return f"{dur:.2f}s" if dur >= 0.05 else "< 1ms"


def _action_text(action):
    """Return title, details for an action."""
    if not action:
        return "Unknown", ""
    kind = _action_kind(action)
    label = (getattr(action, "label", "") or "").strip()
    key = (getattr(action, "key", "") or "").strip()
    repeat = int(getattr(action, "repeat_count", 1) or 1)
    repeat_txt = f" · x{repeat}" if repeat > 1 else ""

    if kind == "pause":
        title = label or "Pause"
        return title, f"Duration: {float(getattr(action, 'duration', 0.0) or 0.0):.2f}s{repeat_txt}"

    if kind == "click":
        button = (getattr(action, "click_button", "left") or "left").title()
        mode = getattr(action, "click_coord_mode", "absolute") or "absolute"
        x, y = getattr(action, "click_x", 0), getattr(action, "click_y", 0)
        rand = int(getattr(action, "click_rand_radius", 0) or 0)
        rand_txt = f" · ±{rand}px" if rand > 0 else ""
        return label or f"{button} Click", f"{mode.title()} · X {x}, Y {y}{rand_txt}{repeat_txt}"

    if kind == "image":
        similarity = float(getattr(action, "similarity", 0.95) or 0.95)
        timeout = float(getattr(action, "wait_timeout", 0.0) or 0.0)
        title = label or "Image Match"
        wait_txt = f" · Wait {timeout:.1f}s" if timeout > 0 else " · Single scan"
        found = getattr(action, "on_found_action", "continue") or "continue"
        return title, f"Threshold: {similarity * 100:.0f}%{wait_txt} · Found: {found.replace('_', ' ')}"

    if kind == "condition":
        ctype = getattr(action, "condition_type", "none") or "none"
        if ctype == "pixel_color":
            detail = f"Pixel @ {getattr(action, 'condition_x', 0)}, {getattr(action, 'condition_y', 0)} = {getattr(action, 'condition_color', '') or 'color'}"
        elif ctype == "variable":
            detail = f"{getattr(action, 'condition_var_name', '') or 'variable'} = {getattr(action, 'condition_var_value', '') or 'value'}"
        else:
            detail = "Condition rule"
        return label or "Condition", detail + repeat_txt

    title = label or (key[:1].upper() + key[1:] if key else "Key")
    hold = " · Hold" if bool(getattr(action, "hold_mode", False)) else ""
    return title, f"Key: {key or 'Unknown'}{hold}{repeat_txt}"


class TimelineDelegate(QStyledItemDelegate):
    """Modern row delegate with per-action progress bars and status chips."""

    def _rounded_rect(self, painter, rect, radius, color, border=None, border_width=1):
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setBrush(QBrush(QColor(color)))
        if border:
            painter.setPen(QPen(QColor(border), border_width))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

    def _draw_type_icon(self, painter, rect, kind, color):
        painter.save()
        c = QColor(color if kind == "image" else COLORS["text"])
        pen = QPen(c, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        if kind == "pause":
            painter.drawEllipse(QRectF(x + w * 0.22, y + h * 0.22, w * 0.56, h * 0.56))
            painter.drawLine(int(x + w * 0.50), int(y + h * 0.34), int(x + w * 0.50), int(y + h * 0.52))
            painter.drawLine(int(x + w * 0.50), int(y + h * 0.52), int(x + w * 0.64), int(y + h * 0.60))
        elif kind == "click":
            painter.drawEllipse(QRectF(x + w * 0.28, y + h * 0.20, w * 0.44, h * 0.62))
            painter.drawLine(int(x + w * 0.50), int(y + h * 0.20), int(x + w * 0.50), int(y + h * 0.42))
            painter.drawLine(int(x + w * 0.28), int(y + h * 0.42), int(x + w * 0.72), int(y + h * 0.42))
        elif kind == "image":
            painter.drawRoundedRect(QRectF(x + w * 0.20, y + h * 0.25, w * 0.60, h * 0.50), 3, 3)
            painter.drawLine(int(x + w * 0.23), int(y + h * 0.62), int(x + w * 0.42), int(y + h * 0.45))
            painter.drawLine(int(x + w * 0.42), int(y + h * 0.45), int(x + w * 0.58), int(y + h * 0.56))
            painter.drawLine(int(x + w * 0.58), int(y + h * 0.56), int(x + w * 0.76), int(y + h * 0.40))
        elif kind == "condition":
            painter.drawPolygon([
                QPointF(x + w * 0.50, y + h * 0.18), QPointF(x + w * 0.82, y + h * 0.50),
                QPointF(x + w * 0.50, y + h * 0.82), QPointF(x + w * 0.18, y + h * 0.50),
            ])
        else:
            painter.drawRoundedRect(QRectF(x + w * 0.18, y + h * 0.28, w * 0.64, h * 0.44), 3, 3)
            for px in (0.30, 0.46, 0.62):
                painter.drawPoint(QPointF(x + w * px, y + h * 0.42))
            painter.drawLine(int(x + w * 0.34), int(y + h * 0.58), int(x + w * 0.66), int(y + h * 0.58))
        painter.restore()

    def paint(self, painter: QPainter, option, index):
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            action = index.data(ActionListModel.ActionRole)
            view = option.widget
            row = index.row()
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
            playing = row == getattr(view, "playing_index", -1)
            progress = _clamp(view.action_progress(row) if hasattr(view, "action_progress") else 0.0)
            kind = _action_kind(action)
            type_color = TYPE_COLORS.get(kind, COLORS.get("accent", "#45c8ff"))

            outer = option.rect.adjusted(24, 4, -38, -4)
            bg = COLORS["bg_card"]
            if hovered:
                bg = _mix(bg, COLORS["bg_hover"], 0.5)
            if selected:
                bg = _mix(bg, COLORS["accent"], 0.15)
            if playing:
                bg = _mix(COLORS["bg_card"], COLORS["accent"], 0.2)

            border = COLORS["border"]
            if selected:
                border = COLORS["border_light"]
            if playing:
                border = COLORS["accent"]
            self._rounded_rect(painter, outer, 6, bg, border, 1.2 if playing else 1)

            # Compact-aware layout. The default app window is 780x780, so the
            # delegate intentionally collapses labels/status metadata before it
            # lets progress bars overlap or clip.
            compact = outer.width() < 720
            tiny = outer.width() < 560

            # Left type accent stripe and active play marker.
            stripe = QRectF(outer.left(), outer.top() + 7, 3.0, outer.height() - 14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(type_color))
            painter.drawRoundedRect(stripe, 1.5, 1.5)
            if playing:
                painter.setBrush(QColor(COLORS["accent"]))
                tri_x = outer.left() + (12 if compact else 18)
                tri_y = outer.center().y()
                painter.drawPolygon([
                    QPointF(tri_x, tri_y - 7), QPointF(tri_x, tri_y + 7), QPointF(tri_x + 10, tri_y)
                ])

            # Drag grip.
            grip_x = outer.left() + (14 if compact else 18)
            grip_y = outer.center().y() - 10
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["text_dark"]))
            for gx in (0, 6):
                for gy in (0, 6, 12):
                    painter.drawEllipse(QRectF(grip_x + gx, grip_y + gy, 2.2, 2.2))

            # Index.
            num_left = outer.left() + (34 if compact else 46)
            num_rect = QRectF(num_left, outer.top(), 28 if compact else 34, outer.height())
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(QFont("Segoe UI", 10 if compact else 12, QFont.Weight.DemiBold))
            painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(row + 1))

            # Icon tile.
            icon_size = 34 if compact else 42
            icon_left = outer.left() + (66 if compact else 90)
            icon_rect = QRectF(icon_left, outer.center().y() - icon_size / 2, icon_size, icon_size)
            path = QPainterPath(); path.addRoundedRect(icon_rect, 8, 8)
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
            painter.setBrush(QBrush(QColor(COLORS["bg"])))
            painter.drawPath(path)
            self._draw_type_icon(painter, icon_rect, kind, type_color)

            # Right-side progress area.
            menu_reserve = 22
            pct_w = 38
            chip_w = 0
            bar_w = int(outer.width() * (0.20 if compact else 0.22))
            bar_w = max(82 if compact else 130, min(190 if compact else 240, bar_w))
            bar_x = outer.right() - menu_reserve - pct_w - chip_w - bar_w - 14
            min_bar_x = icon_rect.right() + 145
            if bar_x < min_bar_x:
                bar_w = max(72, int(outer.right() - menu_reserve - pct_w - chip_w - 14 - min_bar_x))
                bar_x = outer.right() - menu_reserve - pct_w - chip_w - bar_w - 14

            # Title/detail with elision so compact windows remain readable.
            title, detail = _action_text(action)
            text_x = icon_rect.right() + 14
            text_right = max(text_x + 88, bar_x - (104 if compact else 204))
            text_w = max(82, text_right - text_x)
            title_rect = QRectF(text_x, outer.top() + (10 if compact else 12), text_w, 18)
            detail_rect = QRectF(text_x, outer.top() + (31 if compact else 34), text_w, 16)
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(QFont("Segoe UI", 9 if compact else 10, QFont.Weight.DemiBold))
            fm = painter.fontMetrics()
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(title, Qt.TextElideMode.ElideRight, int(text_w)))
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8))
            fm = painter.fontMetrics()
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(detail, Qt.TextElideMode.ElideRight, int(text_w)))

            # Status chip.
            if playing:
                status, status_col = ("Paused", COLORS["pause_cyan"]) if getattr(view, "paused", False) else ("Running", COLORS["success"])
            elif progress >= 0.999:
                status, status_col = "Completed", type_color
            else:
                status, status_col = "Pending", COLORS["text_dim"]

            status_x = bar_x - (90 if compact else 188)
            if compact:
                painter.setBrush(QColor(status_col))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(status_x, outer.center().y() - 4, 8, 8))
            else:
                status_rect = QRectF(status_x, outer.center().y() - 15, 96, 30)
                self._rounded_rect(painter, status_rect, 5, COLORS["bg"], status_col, 1)
                painter.setPen(QColor(status_col))
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, status)

            # Duration metadata; hidden on tiny widths, kept compact otherwise.
            if not tiny:
                dur_x = bar_x - (76 if compact else 76)
                dur_rect = QRectF(dur_x, outer.top(), 58, outer.height())
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.setFont(QFont("Segoe UI", 7 if compact else 8))
                painter.drawText(dur_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, _duration_text(action))

            # Per-action progress bar.
            bar_y = outer.center().y() - 4
            bar_h = 7 if compact else 8
            track = QRectF(bar_x, bar_y, bar_w, bar_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["lane"]))
            painter.drawRoundedRect(track, bar_h / 2, bar_h / 2)
            if progress > 0:
                fill = QRectF(bar_x, bar_y, bar_w * progress, bar_h)
                painter.setBrush(QBrush(QColor(COLORS["accent"] if playing else type_color)))
                painter.drawRoundedRect(fill, bar_h / 2, bar_h / 2)

            pct = f"{int(round(progress * 100)):d}%"
            pct_x = bar_x + bar_w + 8
            painter.setPen(QColor(COLORS["text_dim"] if progress < 1 else COLORS["text"]))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8, QFont.Weight.DemiBold))
            painter.drawText(QRectF(pct_x, outer.top(), pct_w, outer.height()), Qt.AlignmentFlag.AlignVCenter, pct)

            # Image threshold metadata chip.
            if kind == "image" and chip_w:
                sim = int(float(getattr(action, "similarity", 0.95) or 0.95) * 100)
                chip = QRectF(outer.right() - menu_reserve - 42, outer.center().y() - 11, 36, 22)
                self._rounded_rect(painter, chip, 7, COLORS["bg_secondary"], COLORS["border_light"], 1)
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, f"{sim}%")

            # Kebab menu dots.
            dot_x = outer.right() - 20
            painter.setBrush(QColor(COLORS["text_dim"]))
            painter.setPen(Qt.PenStyle.NoPen)
            for dy in (-7, 0, 7):
                painter.drawEllipse(QRectF(dot_x, outer.center().y() + dy - 1.5, 3, 3))
        except Exception as e:
            painter.setBrush(QColor(COLORS.get("bg_secondary", "#202020")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(option.rect)
            painter.setPen(QColor(COLORS.get("text", "#ffffff")))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(option.rect.adjusted(10, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, f"Timeline error: {e}")
        finally:
            painter.restore()

    def sizeHint(self, option, index):
        view = option.widget
        zoom = float(getattr(view, "zoom", 1.0) or 1.0)
        height = max(58, int(78 * zoom))
        return QSize(100, height)


class TimelineView(QListView):
    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)

    def __init__(self, parent=None, model=None):
        super().__init__(parent)

        self.zoom = 1.0
        self.selected_indices = set()
        self.playing_index = -1
        self.paused = False
        self._search = ""
        self._drag_start_row = -1
        self._playing_started = 0.0
        self._playing_duration = 0.0
        self._frozen_progress = 0.0

        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(33)
        self._progress_timer.timeout.connect(self.viewport().update)

        self.setModel(model or ActionListModel())
        self.setItemDelegate(TimelineDelegate(self))
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setAlternatingRowColors(False)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setMinimumHeight(160)
        self.setStyleSheet(
            f"QListView {{ border: none; background-color: {COLORS['bg']}; outline: none; padding: 8px 0; }}"
            f"QListView::item {{ border: none; background: transparent; }}"
        )

        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)
        self.customContextMenuRequested.connect(self._on_context_menu)
        sel = self.selectionModel()
        if sel is not None:
            sel.currentChanged.connect(self._on_current_changed)

    def action_progress(self, row: int) -> float:
        if self.playing_index < 0:
            return 0.0
        if row < self.playing_index:
            return 1.0
        if row > self.playing_index:
            return 0.0
        if self.paused:
            return self._frozen_progress
        if self._playing_duration <= 0.05:
            return 0.6
        return _clamp((time.monotonic() - self._playing_started) / self._playing_duration)

    def _on_current_changed(self, current, previous):
        if current.isValid():
            self.selected_indices = {current.row()}
        else:
            self.selected_indices.clear()
        self.viewport().update()

    def _on_clicked(self, index):
        if index.isValid():
            self.selected_indices = {index.row()}
            self.action_clicked.emit(index.row())

    def _on_double_clicked(self, index):
        if index.isValid():
            self.action_double_clicked.emit(index.row())

    def _on_context_menu(self, pos):
        index = self.indexAt(pos)
        row = index.row() if index.isValid() else -1
        self.action_context_menu.emit(row, self.viewport().mapToGlobal(pos))

    def mousePressEvent(self, event):
        idx = self.indexAt(event.position().toPoint()) if hasattr(event, "position") else self.indexAt(event.pos())
        self._drag_start_row = idx.row() if idx.isValid() else -1
        super().mousePressEvent(event)

    def dropEvent(self, event):
        source = self._drag_start_row
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_index = self.indexAt(pos)
        target = target_index.row() if target_index.isValid() else self.model().rowCount() - 1
        event.ignore()
        if source >= 0 and target >= 0 and source != target:
            QTimer.singleShot(0, lambda s=source, t=target: self.action_dragged.emit(s, t))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            old = self.zoom
            delta = event.angleDelta().y()
            self.zoom = max(0.65, min(1.85, self.zoom * (1.08 if delta > 0 else 1 / 1.08)))
            if self.zoom != old:
                self.setUniformItemSizes(False)
                self.doItemsLayout()
                self.setUniformItemSizes(True)
                self.viewport().update()
            event.accept()
            return
        super().wheelEvent(event)

    def set_actions(self, actions):
        m = self.model()
        if not isinstance(m, ActionListModel):
            m = ActionListModel()
            self.setModel(m)
        if hasattr(m, "set_actions"):
            m.set_actions(actions)
        else:
            m.beginResetModel()
            m._actions = list(actions or [])
            m.endResetModel()
        self.selected_indices.clear()
        self.viewport().update()

    def set_active(self, index):
        if index is not None and 0 <= index < self.model().rowCount():
            idx = self.model().index(index, 0)
            self.setCurrentIndex(idx)
            self.selected_indices = {index}
        else:
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
            self.selected_indices.clear()
        self.viewport().update()

    def set_playing(self, index, duration=0.0):
        self.playing_index = index
        self.paused = False
        self._playing_duration = max(0.0, float(duration or 0.0))
        self._playing_started = time.monotonic()
        self._frozen_progress = 0.0
        if 0 <= index < self.model().rowCount():
            self.scrollTo(self.model().index(index, 0), QAbstractItemView.ScrollHint.EnsureVisible)
        if not self._progress_timer.isActive():
            self._progress_timer.start()
        self.viewport().update()

    def clear_playing(self):
        self.playing_index = -1
        self.paused = False
        self._frozen_progress = 0.0
        if self._progress_timer.isActive():
            self._progress_timer.stop()
        self.viewport().update()

    def set_paused(self, paused: bool):
        paused = bool(paused)
        if paused and not self.paused:
            self._frozen_progress = self.action_progress(self.playing_index)
            if self._progress_timer.isActive():
                self._progress_timer.stop()
        elif not paused and self.paused:
            # Resume without visually jumping the active row.
            self._playing_started = time.monotonic() - (self._frozen_progress * max(self._playing_duration, 0.001))
            if self.playing_index >= 0 and not self._progress_timer.isActive():
                self._progress_timer.start()
        self.paused = paused
        self.viewport().update()

    def ensure_visible(self, index):
        if 0 <= index < self.model().rowCount():
            self.scrollTo(self.model().index(index, 0), QAbstractItemView.ScrollHint.EnsureVisible)

    def set_search(self, text: str):
        self._search = (text or "").strip().lower()
        if not self._search:
            self.viewport().update()
            return
        for row in range(self.model().rowCount()):
            action = self.model().get(row)
            haystack = " ".join(str(getattr(action, name, "") or "") for name in ("label", "key", "action_type"))
            if self._search in haystack.lower():
                self.set_active(row)
                self.ensure_visible(row)
                break
        self.viewport().update()

    def refresh(self):
        self.doItemsLayout()
        self.viewport().update()
