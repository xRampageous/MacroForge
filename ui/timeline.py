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
        title = label or "Delay"
        return title, f"Duration: {float(getattr(action, 'duration', 0.0) or 0.0):.2f}s{repeat_txt}"

    if kind == "click":
        button = (getattr(action, "click_button", "left") or "left").title()
        mode = getattr(action, "click_coord_mode", "absolute") or "absolute"
        x, y = getattr(action, "click_x", 0), getattr(action, "click_y", 0)
        rand = int(getattr(action, "click_rand_radius", 0) or 0)
        rand_txt = f" · ±{rand}px" if rand > 0 else ""
        return label or f"{button} Click", f"{mode.title()} · X {x}, Y {y}{rand_txt}{repeat_txt}"

    if kind == "image":
        return label or "Image", "Template.png"

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

            narrow = option.rect.width() < 700
            # Compact timeline treatment: tighter outer padding keeps more rows
            # visible at once without changing the overall layout structure.
            outer = option.rect.adjusted(8, 2, -8, -2) if narrow else option.rect.adjusted(14, 3, -20, -3)
            bg = COLORS["bg_card"]
            if hovered:
                bg = _mix(bg, COLORS["bg_hover"], 0.5)
            if selected:
                bg = _mix(bg, type_color, 0.12)

            border = COLORS["border"]
            if selected:
                border = COLORS["border_light"]
            if playing:
                border = type_color

            # Active rows use a richer action-colour gradient: strong left block,
            # soft centre glow, and dark right fade. This keeps the action colour
            # obvious without hurting text readability.
            if playing:
                row_path = QPainterPath()
                row_path.addRoundedRect(QRectF(outer), 8, 8)

                row_grad = QLinearGradient(QPointF(outer.left(), outer.top()), QPointF(outer.right(), outer.top()))
                left_col = QColor(type_color); left_col.setAlpha(205)
                hot_col = QColor(_mix(type_color, "#ffffff", 0.18)); hot_col.setAlpha(132)
                mid_col = QColor(type_color); mid_col.setAlpha(54)
                dim_col = QColor(type_color); dim_col.setAlpha(16)
                row_grad.setColorAt(0.00, left_col)
                row_grad.setColorAt(0.10, hot_col)
                row_grad.setColorAt(0.28, mid_col)
                row_grad.setColorAt(0.58, dim_col)
                row_grad.setColorAt(1.00, QColor(COLORS["bg_card"]))

                painter.setBrush(QBrush(row_grad))
                painter.setPen(QPen(QColor(type_color), 1.6))
                painter.drawPath(row_path)

                # Thin top sheen gives the active row a sleeker, less flat look.
                sheen = QLinearGradient(QPointF(outer.left(), outer.top()), QPointF(outer.right(), outer.top()))
                sheen_col = QColor("#ffffff"); sheen_col.setAlpha(44)
                clear_col = QColor("#ffffff"); clear_col.setAlpha(0)
                sheen.setColorAt(0.00, sheen_col)
                sheen.setColorAt(0.30, QColor(type_color).lighter(130))
                sheen.setColorAt(1.00, clear_col)
                painter.setPen(QPen(QBrush(sheen), 1.0))
                painter.drawLine(QPointF(outer.left() + 7, outer.top() + 1), QPointF(outer.right() - 7, outer.top() + 1))
            else:
                self._rounded_rect(painter, outer, 8, bg, border, 1)

            # Compact-aware layout. The default app window is 780x780, so the
            # delegate intentionally collapses labels/status metadata before it
            # lets progress bars overlap or clip.
            compact = outer.width() < 760
            tiny = outer.width() < 600

            # Left type accent stripe and active play marker. Active playback fills
            # the row's left end with the action's own gradient colour.
            if playing:
                painter.save()
                clip_path = QPainterPath()
                clip_path.addRoundedRect(QRectF(outer), 8, 8)
                painter.setClipPath(clip_path)

                active_w = (112 if compact else 150)
                active_rect = QRectF(outer.left(), outer.top(), active_w, outer.height())
                left_grad = QLinearGradient(QPointF(active_rect.left(), active_rect.top()), QPointF(active_rect.right(), active_rect.top()))
                left_a = QColor(_mix(type_color, "#ffffff", 0.16)); left_a.setAlpha(238)
                left_b = QColor(type_color); left_b.setAlpha(168)
                left_c = QColor(type_color); left_c.setAlpha(18)
                left_grad.setColorAt(0.00, left_a)
                left_grad.setColorAt(0.22, left_b)
                left_grad.setColorAt(1.00, left_c)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(left_grad))
                painter.drawRect(active_rect)

                # Bright active edge, matching the Add Action button colour.
                edge = QRectF(outer.left(), outer.top() + 1, 4, outer.height() - 2)
                painter.setBrush(QColor(type_color))
                painter.drawRoundedRect(edge, 2, 2)
                painter.restore()

            stripe = QRectF(outer.left(), outer.top() + 1, 3.0, outer.height() - 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(type_color))
            painter.drawRoundedRect(stripe, 1.5, 1.5)
            if playing:
                painter.setBrush(QColor(type_color))
                tri_x = outer.left() + (10 if compact else 14)
                tri_y = outer.center().y()
                painter.drawPolygon([
                    QPointF(tri_x, tri_y - 5), QPointF(tri_x, tri_y + 5), QPointF(tri_x + 8, tri_y)
                ])

            # Drag grip.
            grip_x = outer.left() + (12 if compact else 16)
            grip_y = outer.center().y() - 8
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["text_dark"]))
            for gx in (0, 5):
                for gy in (0, 5, 10):
                    painter.drawEllipse(QRectF(grip_x + gx, grip_y + gy, 2.0, 2.0))

            # Index.
            num_left = outer.left() + (28 if compact else 46)
            num_rect = QRectF(num_left, outer.top(), 26 if compact else 30, outer.height())
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(QFont("Segoe UI", 9 if compact else 10, QFont.Weight.DemiBold))
            painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(row + 1))

            # Icon tile.
            icon_size = 28 if compact else 34
            icon_left = outer.left() + (54 if compact else 82)
            icon_rect = QRectF(icon_left, outer.center().y() - icon_size / 2, icon_size, icon_size)
            path = QPainterPath(); path.addRoundedRect(icon_rect, 8, 8)
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
            painter.setBrush(QBrush(QColor(COLORS["bg"])))
            painter.drawPath(path)
            self._draw_type_icon(painter, icon_rect, kind, type_color)

            # Right-side progress area. Status/duration are fixed-size columns;
            # only the progress rail itself expands/contracts with window width.
            menu_reserve = 22 if compact else 26
            pct_w = 38 if compact else 44
            right_edge = outer.right() - menu_reserve - pct_w - 10

            status_w = 14 if compact else 92
            status_x = max(icon_rect.right() + 96, outer.left() + int(outer.width() * (0.52 if compact else 0.49)))
            duration_w = 48 if compact else 56
            bar_x = max(status_x + status_w + (42 if tiny else 62), outer.left() + int(outer.width() * (0.70 if compact else 0.66)))
            if not tiny:
                bar_x = max(bar_x, status_x + status_w + duration_w + 18)
            bar_w = max(64 if compact else 96, int(right_edge - bar_x))
            if bar_x + bar_w > right_edge:
                bar_w = max(56, int(right_edge - bar_x))

            # Title/detail with elision so compact windows remain readable.
            title, detail = _action_text(action)
            text_x = icon_rect.right() + 14
            text_right = max(text_x + 72, status_x - 14)
            text_w = max(72, text_right - text_x)
            title_rect = QRectF(text_x, outer.top() + (7 if compact else 9), text_w, 17)
            detail_rect = QRectF(text_x, outer.top() + (22 if compact else 26), text_w, 14)
            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(QFont("Segoe UI", 8 if compact else 9, QFont.Weight.DemiBold))
            fm = painter.fontMetrics()
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(title, Qt.TextElideMode.ElideRight, int(text_w)))
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8))
            fm = painter.fontMetrics()
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(detail, Qt.TextElideMode.ElideRight, int(text_w)))

            # Status chip / dot. Its width is fixed; it does not resize with the row.
            if playing:
                status, status_col = ("Paused", COLORS["pause_cyan"]) if getattr(view, "paused", False) else ("Running", type_color)
            elif progress >= 0.999:
                status, status_col = "Completed", type_color
            else:
                status, status_col = "Pending", COLORS["text_dim"]

            if compact:
                painter.setBrush(QColor(status_col))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(status_x, outer.center().y() - 4, 8, 8))
            else:
                status_rect = QRectF(status_x, outer.center().y() - 15, status_w, 30)
                self._rounded_rect(painter, status_rect, 5, COLORS["bg"], status_col, 1)
                painter.setPen(QColor(status_col))
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
                painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, status)

            # Duration metadata; fixed-size column before progress rail.
            if not tiny:
                dur_x = bar_x - duration_w - 12
                dur_rect = QRectF(dur_x, outer.top(), duration_w, outer.height())
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.setFont(QFont("Segoe UI", 7 if compact else 8))
                painter.drawText(dur_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, _duration_text(action))

            # Per-action progress bar. This is the responsive part of the row.
            bar_y = outer.center().y() - 3
            bar_h = 6 if compact else 7
            track = QRectF(bar_x, bar_y, bar_w, bar_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["lane"]))
            painter.drawRoundedRect(track, bar_h / 2, bar_h / 2)
            if progress > 0:
                fill = QRectF(bar_x, bar_y, bar_w * progress, bar_h)
                painter.setBrush(QBrush(QColor(type_color)))
                painter.drawRoundedRect(fill, bar_h / 2, bar_h / 2)

            pct = f"{int(round(progress * 100)):d}%"
            pct_x = bar_x + bar_w + 8
            painter.setPen(QColor(COLORS["text_dim"] if progress < 1 else COLORS["text"]))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8, QFont.Weight.DemiBold))
            painter.drawText(QRectF(pct_x, outer.top(), pct_w, outer.height()), Qt.AlignmentFlag.AlignVCenter, pct)

            # Image threshold metadata chip intentionally removed. Image rows now
            # show the template name in the detail text, avoiding cramped metadata.
            # Kebab menu dots.
            dot_x = outer.right() - (16 if compact else 22)
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
        base_height = 56 if getattr(option.widget, "width", lambda: 999)() < 700 else 64
        height = max(48, int(base_height * zoom))
        return QSize(100, height)


class TimelineView(QListView):
    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)

    def __init__(self, parent=None, model=None):
        super().__init__(parent)

        # Start slightly compact by default while preserving Ctrl+wheel zoom.
        self.zoom = 0.90
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
            f"QListView {{ border: none; background-color: {COLORS['bg']}; outline: none; padding: 0; }}"
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
            self.zoom = max(0.55, min(1.60, self.zoom * (1.08 if delta > 0 else 1 / 1.08)))
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
