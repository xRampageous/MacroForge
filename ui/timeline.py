"""MacroForge Timeline — high-performance polished action list.

This QListView timeline keeps the public API used by main_window.py while
rendering a modern, information-rich action row using one lightweight delegate.
It intentionally avoids widgets-per-row so large macros remain fast.
"""

import time
from PyQt6.QtWidgets import QStyledItemDelegate, QListView, QAbstractItemView, QStyle
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QSize, QTimer, QRectF, QPointF, QItemSelectionModel
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPainterPath, QLinearGradient

from ui.theme import COLORS, TYPE_COLORS
from models import ActionListModel

TIMELINE_PROGRESS_COLUMN_SHIFT = 20
TIMELINE_MULTI_SELECT_RAIL_WIDTH = 6

IMAGE_STATE_DISPLAY = {
    "Waiting": ("SCAN", "Searching", "neon_gold"),
    "Found": ("DONE", "Matched", "success"),
    "Missed": ("FAIL", "Failed", "error"),
    "Timeout": ("TIME", "Timeout", "error"),
}


def _safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, _safe_float(value, lo)))


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    """Blend two #RRGGBB colours."""
    t = _clamp(t)
    a = QColor(hex_a)
    b = QColor(hex_b)
    r = int(a.red() + (b.red() - a.red()) * t)
    g = int(a.green() + (b.green() - a.green()) * t)
    bl = int(a.blue() + (b.blue() - a.blue()) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def _pulse(speed=1.0, floor=0.0, ceiling=1.0) -> float:
    """Cheap saw/ping-pong pulse used by the active row polish."""
    span = max(0.001, ceiling - floor)
    phase = (time.time() * max(0.05, speed)) % 2.0
    value = 1.0 - abs(phase - 1.0)
    return floor + value * span


def _image_state_meta(state: str):
    """Return (status_code, friendly_label, colour) for image runtime states."""
    code, label, color_key = IMAGE_STATE_DISPLAY.get(str(state or ""), ("", str(state or ""), "text_dim"))
    return code, label, COLORS.get(color_key, COLORS.get("text_dim", "#8a94a8"))


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
    dur = _safe_float(getattr(action, "duration", 0.0), 0.0)
    if kind == "pause":
        return f"{dur:.2f}s"
    if kind == "image":
        timeout = _safe_float(getattr(action, "wait_timeout", 0.0), 0.0)
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
    repeat = _safe_int(getattr(action, "repeat_count", 1), 1)
    repeat_txt = f" · x{repeat}" if repeat > 1 else ""

    if kind == "pause":
        title = label or "Delay"
        return title, f"Repeat x{repeat}" if repeat > 1 else ""

    if kind == "click":
        button = (getattr(action, "click_button", "left") or "left").title()
        x, y = getattr(action, "click_x", 0), getattr(action, "click_y", 0)
        rand = _safe_int(getattr(action, "click_rand_radius", 0), 0)
        rand_txt = f" · ±{rand}px" if rand > 0 else ""
        return label or f"{button} Click", f"X {x}, Y {y}{rand_txt}{repeat_txt}"

    if kind == "image":
        # Image template filenames stay available in the inspector/action dialog.
        # The timeline row hides them so the compact placement has room for
        # confidence metadata and the status column.
        return label or "Image", ""

    if kind == "group":
        name = label or getattr(action, "group_name", "") or "Folder"
        return name, ""

    if kind == "loop":
        count = _safe_int(getattr(action, "loop_count", getattr(action, "repeat_count", 2)), 2)
        target = _safe_int(getattr(action, "loop_target", -1), -1)
        detail = f"Repeat x{count}"
        if target >= 0:
            detail += f" · back to row {target + 1}"
        return label or "Loop block", detail

    if kind == "condition":
        ctype = getattr(action, "condition_type", "none") or "none"
        if ctype == "pixel_color":
            detail = f"Pixel {getattr(action, 'condition_x', 0)},{getattr(action, 'condition_y', 0)}"
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
        elif kind == "group":
            painter.drawRoundedRect(QRectF(x + w * 0.18, y + h * 0.34, w * 0.64, h * 0.40), 3, 3)
            painter.drawLine(int(x + w * 0.25), int(y + h * 0.34), int(x + w * 0.36), int(y + h * 0.25))
            painter.drawLine(int(x + w * 0.36), int(y + h * 0.25), int(x + w * 0.54), int(y + h * 0.25))
        elif kind == "loop":
            painter.drawArc(int(x + w * 0.22), int(y + h * 0.24), int(w * 0.56), int(h * 0.52), 35 * 16, 285 * 16)
            painter.drawLine(int(x + w * 0.70), int(y + h * 0.30), int(x + w * 0.82), int(y + h * 0.30))
            painter.drawLine(int(x + w * 0.82), int(y + h * 0.30), int(x + w * 0.77), int(y + h * 0.42))
        else:
            painter.drawRoundedRect(QRectF(x + w * 0.18, y + h * 0.28, w * 0.64, h * 0.44), 3, 3)
            for px in (0.30, 0.46, 0.62):
                painter.drawPoint(QPointF(x + w * px, y + h * 0.42))
            painter.drawLine(int(x + w * 0.34), int(y + h * 0.58), int(x + w * 0.66), int(y + h * 0.58))
        painter.restore()

    def _row_rects(self, view, row: int, option_rect):
        """Return full row, painted card, and grouped-gutter geometry.

        Grouped child rows are visually cut in from the left so the far-left
        gutter contains only the group connector rail/node.  The returned card
        rect is used for all card fills, active overlays, stripe, grip, text,
        progress and right controls.
        """
        narrow = option_rect.width() < 700
        full = option_rect.adjusted(8, 2, -8, -2) if narrow else option_rect.adjusted(14, 3, -20, -3)
        full = QRectF(full)
        compact = full.width() < 760
        actions = view._actions() if hasattr(view, "_actions") else []
        action = actions[row] if 0 <= row < len(actions) else None
        meta = view.group_badge(row) if hasattr(view, "group_badge") else None
        child_group = bool(meta and action is not None and getattr(action, "action_type", "") != "group")
        cut = (38 if compact else 48) if child_group else 0
        card = QRectF(full)
        if cut:
            card.adjust(cut, 0, 0, 0)
        return {"full": full, "card": card, "compact": compact, "child_group": child_group, "cut": cut, "group_badge": meta}

    def paint(self, painter: QPainter, option, index):
        painter.save()
        try:
            view = option.widget
            row = index.row()
            if hasattr(view, "is_row_collapsed_hidden") and view.is_row_collapsed_hidden(row):
                return
            if hasattr(view, "is_row_filtered_hidden") and view.is_row_filtered_hidden(row):
                return
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            action = index.data(ActionListModel.ActionRole)
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            multi_select = (
                view.multi_selection_visual_state(row)
                if hasattr(view, "multi_selection_visual_state")
                else {"active": False, "count": 0, "has_previous": False, "has_next": False}
            )
            multi_selected = bool(multi_select.get("active"))
            hovered = row == getattr(view, "hover_row", -1)
            playing = row == getattr(view, "playing_index", -1)
            queued = row == getattr(view, "next_index", -1)
            drag_rows = set(getattr(view, "drag_source_rows", []) or [])
            dragging = row == getattr(view, "drag_source_row", -1) or row in drag_rows
            group_drop_target = row == getattr(view, "drop_group_row", -1)
            flashed = row == getattr(view, "flash_row", -1)
            flash_opacity = float(getattr(view, "flash_opacity", 0.0) or 0.0)
            traced = row in getattr(view, "trace_rows", set())
            linked_source = row == getattr(view, "link_source_row", -1)
            linked_target = row in getattr(view, "link_target_rows", set())
            search_query = str(getattr(view, "_search", "") or "").strip()
            remembered_search_match = row in getattr(view, "_search_highlight_rows", set())
            search_match = bool(
                (search_query and hasattr(view, "_row_matches_search") and view._row_matches_search(row))
                or remembered_search_match
            )
            current_search_match = bool(search_match and row == getattr(view, "_search_current_row", -1))
            invalid_group_drop = bool(group_drop_target and not getattr(view, "drop_feedback_valid", False))
            progress = _clamp(view.action_progress(row) if hasattr(view, "action_progress") else 0.0)
            kind = _action_kind(action)
            if kind == "group" and hasattr(view, "group_progress"):
                progress = _clamp(view.group_progress(row).get("progress", progress))
            group_badge = view.group_badge(row) if hasattr(view, "group_badge") else None
            active_group = bool(
                kind == "group"
                and getattr(view, "active_group_id", "")
                and getattr(action, "group_id", "") == getattr(view, "active_group_id", "")
            )
            type_color = TYPE_COLORS.get(kind, COLORS.get("accent", "#45c8ff"))
            if group_badge and group_badge.get("color") and kind != "group":
                type_color = group_badge.get("color")
            enabled = bool(getattr(action, "enabled", True))
            if not enabled:
                type_color = _mix(type_color, COLORS["text_dark"], 0.62)

            row_rects = self._row_rects(view, row, option.rect)
            full_outer = row_rects["full"]
            outer = row_rects["card"]
            compact = bool(row_rects["compact"])
            child_group = group_badge if row_rects["child_group"] else None

            painter.setClipRect(option.rect.adjusted(-1, -1, 1, 1))

            bg = COLORS["bg_card"]
            if not enabled:
                bg = _mix(bg, COLORS["bg"], 0.72)
            if hovered:
                bg = _mix(bg, COLORS["bg_hover"], 0.5)
            if multi_selected and not playing:
                bg = _mix(bg, COLORS.get("accent", type_color), 0.24)
            if selected and hovered:
                bg = _mix(bg, type_color, 0.12)
            if queued or active_group:
                bg = _mix(bg, type_color, 0.07 if queued else 0.10)
            if dragging:
                bg = _mix(bg, type_color, 0.18)
                full_outer.translate(0, -2)
                outer.translate(0, -2)
            if traced and not playing:
                bg = _mix(bg, COLORS.get("success", type_color), 0.07)
            if linked_source and not playing:
                bg = _mix(bg, type_color, 0.10)
            if linked_target and not playing:
                bg = _mix(bg, COLORS.get("accent", type_color), 0.13)
            if search_match and not playing:
                strength = 0.07 if remembered_search_match and not search_query else 0.10
                bg = _mix(bg, COLORS.get("accent", type_color), strength if not current_search_match else 0.18)
            if group_drop_target and kind == "group" and not playing and not invalid_group_drop:
                bg = _mix(bg, COLORS.get("success", type_color), 0.18)
            if invalid_group_drop and kind == "group" and not playing:
                bg = _mix(bg, COLORS.get("error", "#ff3142"), 0.18)
            if flashed:
                bg = _mix(bg, type_color, 0.22 * flash_opacity)

            border = COLORS["border"]
            if selected and hovered:
                border = COLORS["border_light"]
            if multi_selected and not playing:
                border = COLORS.get("accent", type_color)
            if queued:
                border = _mix(COLORS["border"], type_color, 0.35)
            if traced:
                border = _mix(COLORS["border"], COLORS.get("success", type_color), 0.34)
            if linked_source:
                border = _mix(COLORS["border_light"], type_color, 0.55)
            if linked_target:
                border = COLORS.get("accent", type_color)
            if search_match and search_query:
                border = COLORS.get("accent", type_color)
            if current_search_match:
                border = COLORS.get("warning", COLORS.get("accent", type_color))
            if group_drop_target and kind == "group" and not invalid_group_drop:
                border = COLORS.get("success", type_color)
            if invalid_group_drop and kind == "group":
                border = COLORS.get("error", "#ff3142")
            if dragging or flashed:
                border = _mix(COLORS["border_light"], type_color, 0.55)
            if playing:
                border = type_color

            if kind == "group" and not playing:
                bg = _mix(COLORS["bg_card"], type_color, 0.14)
                border = _mix(COLORS["border_light"], type_color, 0.45)
                if invalid_group_drop:
                    bg = _mix(COLORS["bg_card"], COLORS.get("error", "#ff3142"), 0.18)
                    border = COLORS.get("error", "#ff3142")

            # Active rows use a richer action-colour gradient: strong left block,
            # soft centre glow, subtle scan sweep and dark right fade. This keeps
            # the action colour obvious without hurting text readability.
            if playing:
                row_path = QPainterPath()
                row_path.addRoundedRect(QRectF(outer), 8, 8)
                pulse = _pulse(speed=1.15, floor=0.35, ceiling=1.0)

                # Soft outer halo before the card fill gives the active row a
                # premium illuminated edge while still clipping inside the row.
                for width, alpha in ((6.0, int(30 + 32 * pulse)), (2.2, int(120 + 55 * pulse))):
                    halo = QColor(type_color)
                    halo.setAlpha(alpha)
                    painter.setPen(QPen(halo, width))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(QRectF(outer).adjusted(1.8, 1.8, -1.8, -1.8), 8, 8)

                row_grad = QLinearGradient(QPointF(outer.left(), outer.top()), QPointF(outer.right(), outer.top()))
                left_col = QColor(_mix(type_color, "#ffffff", 0.26)); left_col.setAlpha(230)
                hot_col = QColor(type_color); hot_col.setAlpha(174)
                mid_col = QColor(type_color); mid_col.setAlpha(68)
                dim_col = QColor(type_color); dim_col.setAlpha(18)
                row_grad.setColorAt(0.00, left_col)
                row_grad.setColorAt(0.13, hot_col)
                row_grad.setColorAt(0.34, mid_col)
                row_grad.setColorAt(0.66, dim_col)
                row_grad.setColorAt(1.00, QColor(COLORS["bg_card"]))

                painter.setBrush(QBrush(row_grad))
                painter.setPen(QPen(QColor(type_color), 1.8))
                painter.drawPath(row_path)

                # Animated diagonal/linear sweep. It is clipped to the row so the
                # effect cannot bleed into adjacent timeline rows.
                painter.save()
                painter.setClipPath(row_path)
                sweep_w = max(42.0, outer.width() * 0.18)
                sweep_x = outer.left() - sweep_w + (outer.width() + sweep_w * 2) * ((time.time() * 0.34) % 1.0)
                sweep = QLinearGradient(QPointF(sweep_x, outer.top()), QPointF(sweep_x + sweep_w, outer.bottom()))
                clear = QColor("#ffffff"); clear.setAlpha(0)
                shine = QColor("#ffffff"); shine.setAlpha(int(18 + 18 * pulse))
                sweep.setColorAt(0.00, clear)
                sweep.setColorAt(0.48, shine)
                sweep.setColorAt(1.00, clear)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(sweep))
                painter.drawRect(QRectF(sweep_x, outer.top(), sweep_w, outer.height()))
                painter.restore()

                # Thin top sheen gives the active row a sleeker, less flat look.
                sheen = QLinearGradient(QPointF(outer.left(), outer.top()), QPointF(outer.right(), outer.top()))
                sheen_col = QColor("#ffffff"); sheen_col.setAlpha(54)
                color_sheen = QColor(_mix(type_color, "#ffffff", 0.42)); color_sheen.setAlpha(52)
                clear_col = QColor("#ffffff"); clear_col.setAlpha(0)
                sheen.setColorAt(0.00, sheen_col)
                sheen.setColorAt(0.28, color_sheen)
                sheen.setColorAt(1.00, clear_col)
                painter.setPen(QPen(QBrush(sheen), 1.0))
                painter.drawLine(QPointF(outer.left() + 7, outer.top() + 1), QPointF(outer.right() - 7, outer.top() + 1))
            else:
                if dragging:
                    shadow = QRectF(outer)
                    shadow.translate(0, 4)
                    shadow_col = QColor("#000000")
                    shadow_col.setAlpha(95)
                    self._rounded_rect(painter, shadow, 8, shadow_col.name(QColor.NameFormat.HexArgb))
                self._rounded_rect(painter, outer, 8, bg, border, 1)

            if multi_selected:
                painter.save()
                rail_col = QColor(COLORS.get("accent", type_color))
                rail_col.setAlpha(255 if selected else 232)
                rail_x = outer.left() + (6 if compact else 8)
                rail_w = TIMELINE_MULTI_SELECT_RAIL_WIDTH
                rail_top = outer.top() + (0 if multi_select.get("has_previous") else 7)
                rail_bottom = outer.bottom() - (0 if multi_select.get("has_next") else 7)
                rail = QRectF(rail_x, rail_top, rail_w, max(8, rail_bottom - rail_top))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(rail_col)
                painter.drawRoundedRect(rail, rail_w / 2, rail_w / 2)

                node_r = 4.8 if compact else 5.4
                node = QRectF(
                    rail_x + rail_w / 2 - node_r,
                    outer.center().y() - node_r,
                    node_r * 2,
                    node_r * 2,
                )
                painter.setBrush(QColor(COLORS["bg"]))
                painter.drawEllipse(node.adjusted(-1.2, -1.2, 1.2, 1.2))
                painter.setBrush(rail_col)
                painter.drawEllipse(node)

                if selected:
                    glow = QColor(COLORS.get("accent", type_color))
                    glow.setAlpha(135)
                    painter.setPen(QPen(glow, 1.8))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(QRectF(outer).adjusted(1.5, 1.5, -1.5, -1.5), 7, 7)
                painter.restore()

            if current_search_match and not playing:
                glow_rect = QRectF(outer).adjusted(1.5, 1.5, -1.5, -1.5)
                glow_col = QColor(COLORS.get("warning", COLORS.get("accent", type_color)))
                glow_col.setAlpha(150)
                painter.setPen(QPen(glow_col, 1.7))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(glow_rect, 7, 7)

            # Compact-aware layout. Timeline metadata stays visible at every
            # supported window size; only the progress rail flexes horizontally.
            # Grouped child rows already use a cut-in card rect, so all child
            # content starts at the card left while the connector rail stays in
            # the untouched gutter.
            child_indent = 0

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

            # Expanded group connector rail. Grouped child rows now have a
            # cut-in painted card, leaving the far-left gutter exclusively for
            # rail + node + short branch.
            if child_group:
                actions = view._actions() if hasattr(view, "_actions") else []
                gid = child_group.get("gid", "")
                rail_x = full_outer.left() + (16 if compact else 20)
                node_r = 3.5 if compact else 4.0
                rail_col = QColor(child_group.get("color") or type_color)
                rail_col.setAlpha(154)

                def same_visible_child(candidate_row: int) -> bool:
                    if candidate_row < 0 or candidate_row >= len(actions):
                        return False
                    candidate = actions[candidate_row]
                    if getattr(candidate, "action_type", "") == "group":
                        return False
                    if getattr(candidate, "group_id", "") != gid:
                        return False
                    if hasattr(view, "is_row_collapsed_hidden") and view.is_row_collapsed_hidden(candidate_row):
                        return False
                    if hasattr(view, "is_row_filtered_hidden") and view.is_row_filtered_hidden(candidate_row):
                        return False
                    return True

                def visible_child_before() -> bool:
                    for candidate_row in range(row - 1, -1, -1):
                        candidate = actions[candidate_row] if candidate_row < len(actions) else None
                        if getattr(candidate, "action_type", "") == "group" and getattr(candidate, "group_id", "") == gid:
                            return False
                        if getattr(candidate, "group_id", "") not in (gid, "") and getattr(candidate, "action_type", "") == "group":
                            return False
                        if same_visible_child(candidate_row):
                            return True
                    return False

                def visible_child_after() -> bool:
                    for candidate_row in range(row + 1, len(actions)):
                        candidate = actions[candidate_row]
                        if getattr(candidate, "action_type", "") == "group":
                            return False
                        if getattr(candidate, "group_id", "") != gid:
                            return False
                        if same_visible_child(candidate_row):
                            return True
                    return False

                has_prev = visible_child_before()
                has_next = visible_child_after()
                center_y = full_outer.center().y()
                top_y = full_outer.top() - 2 if has_prev else full_outer.top() + 8
                bottom_y = full_outer.bottom() + 2 if has_next else center_y
                branch_end = max(rail_x + 12, outer.left() - (5 if compact else 6))

                painter.save()
                painter.setClipRect(option.rect.adjusted(-2, -2, 2, 2))
                painter.setPen(QPen(rail_col, 1.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(QPointF(rail_x, top_y), QPointF(rail_x, center_y))
                painter.drawLine(QPointF(rail_x, center_y), QPointF(rail_x, bottom_y))
                painter.drawLine(QPointF(rail_x, center_y), QPointF(branch_end, center_y))
                painter.setPen(Qt.PenStyle.NoPen)
                node_fill = QColor(COLORS["bg_card"])
                node_fill.setAlpha(245)
                painter.setBrush(node_fill)
                painter.drawEllipse(QRectF(rail_x - node_r, center_y - node_r, node_r * 2, node_r * 2))
                painter.setBrush(rail_col)
                painter.drawEllipse(QRectF(rail_x - 2.2, center_y - 2.2, 4.4, 4.4))
                painter.restore()

            stripe_left = outer.left() + child_indent
            stripe = QRectF(stripe_left, outer.top() + 1, 3.0, outer.height() - 2)
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

            # Drag grip. Grouped child rows move the grip after the coloured
            # stripe so the dots are no longer clipped by the connector gutter.
            grip_x = (stripe.right() + (8 if compact else 10)) if child_group else (outer.left() + (12 if compact else 16))
            grip_y = outer.center().y() - 8
            painter.setPen(Qt.PenStyle.NoPen)
            grip_color = "#000000" if playing else (COLORS["border_light"] if getattr(view, "playing_index", -1) >= 0 else COLORS["text_dark"])
            painter.setBrush(QColor(grip_color))
            for gx in (0, 5):
                for gy in (0, 5, 10):
                    painter.drawEllipse(QRectF(grip_x + gx, grip_y + gy, 2.0, 2.0))

            # Index.
            num_left = outer.left() + (28 if compact else 46) + child_indent
            num_rect = QRectF(num_left, outer.top(), 26 if compact else 30, outer.height())
            num_color = "#000000" if playing else COLORS["text"]
            painter.setPen(QColor(num_color))
            painter.setFont(QFont("Segoe UI", 9 if compact else 10, QFont.Weight.DemiBold))
            painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(row + 1))

            # Icon tile.
            icon_size = 28 if compact else 34
            icon_left = outer.left() + (54 if compact else 82) + child_indent
            if kind == "group":
                icon_rect = QRectF(icon_left, outer.top() + (7 if compact else 8), icon_size, icon_size)
            else:
                icon_rect = QRectF(icon_left, outer.center().y() - icon_size / 2, icon_size, icon_size)
            path = QPainterPath(); path.addRoundedRect(icon_rect, 8, 8)
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
            painter.setBrush(QBrush(QColor(COLORS["bg"])))
            painter.drawPath(path)
            self._draw_type_icon(painter, icon_rect, kind, type_color)

            # Right-side progress area. Status and duration are static columns;
            # only the progress rail expands/contracts with window width.  The
            # status pill keeps its right edge locked and expands left for
            # longer runtime labels so duration/progress never jump sideways.
            menu_reserve = 22 if compact else 26
            pct_w = 38 if compact else 44
            right_edge = outer.right() - menu_reserve - pct_w - 10

            image_state_raw = str(getattr(view, "image_states", {}).get(row, "") or "") if kind == "image" else ""
            image_status, image_detail_label, image_state_color = _image_state_meta(image_state_raw)
            if not enabled:
                status, status_col = "SKIP", COLORS["text_dark"]
            elif kind == "group":
                # Drop interaction text is emitted to the top-right status pill;
                # group row status stays stable/aligned during drag targeting.
                status, status_col = ("ACTIVE", type_color) if active_group else ("FOLDER", type_color)
            elif kind == "loop":
                status, status_col = "LOOP", type_color
            elif playing:
                status, status_col = ("PAUSE", COLORS["pause_cyan"]) if getattr(view, "paused", False) else ("RUN", type_color)
            elif kind == "image" and image_status:
                status, status_col = image_status, image_state_color
            elif progress >= 0.999:
                status, status_col = "DONE", type_color
            else:
                status, status_col = "WAIT", COLORS["text_dim"]

            status_base_w = 64 if compact else 78
            # Use one invisible global column system for normal rows, group
            # headers and cut-in child rows.  Child cards remain indented on
            # the left, but status/duration/progress stay table-aligned.
            status_right = full_outer.left() + (292 if compact else 392) + TIMELINE_PROGRESS_COLUMN_SHIFT
            status_font = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
            painter.setFont(status_font)
            status_text_w = painter.fontMetrics().horizontalAdvance(status)
            status_max_w = 126 if compact else 154
            status_w = max(status_base_w, min(status_max_w, status_text_w + (28 if compact else 34)))
            status_x = status_right - status_w
            conf_w = 48 if compact else 58
            conf_gap = 3 if compact else 4
            conf_rect = QRectF(status_x - conf_w - conf_gap, outer.center().y() - 8, conf_w, 16) if kind == "image" else QRectF()
            duration_w = 46 if compact else 56
            dur_x = status_right + 10
            bar_x = dur_x + duration_w + 10
            bar_w = max(28, int(right_edge - bar_x))

            # Title/detail with elision so compact windows remain readable.
            title, detail = _action_text(action)
            detail_color = COLORS["text_dim"]
            image_match_state = ""
            image_match_color = COLORS["text_dim"]
            if kind == "image":
                image_match_state = image_state_raw
                if image_match_state:
                    _, image_match_label, image_match_color = _image_state_meta(image_match_state)
                    # Image runtime tests sit under the row name, not as a
                    # separate floating chip, so the timeline stays compact.
                    detail = image_match_label
                    detail_color = image_match_color
            if kind == "group" and group_badge:
                count = _safe_int(group_badge.get("count", 0), 0)
                detail = f"{count} Action{'s' if count != 1 else ''}"
            if kind == "loop" and hasattr(view, "group_badge"):
                target = _safe_int(getattr(action, "loop_target", -1), -1)
                meta = view.group_badge(target) if target >= 0 else None
                count = _safe_int(getattr(action, "loop_count", getattr(action, "repeat_count", 2)), 2)
                if meta:
                    detail = f"Repeat x{count} · back to {meta.get('badge', 'F')} {meta.get('name', 'Folder')}"
            depth = max(0, _safe_int(getattr(action, "block_depth", 0), 0))
            text_x = icon_rect.right() + 14 + min(depth, 4) * 12
            text_right_limit = (conf_rect.left() - 10) if kind == "image" and not conf_rect.isNull() else (status_x - 14)
            if kind == "image" and not conf_rect.isNull():
                text_right = max(text_x + (42 if compact else 58), text_right_limit)
                if text_right_limit > text_x + 28:
                    text_right = min(text_right, text_right_limit)
                text_w = max(28, text_right - text_x)
            else:
                text_right = max(text_x + 72, text_right_limit)
                text_w = max(72, text_right - text_x)
            title_rect = QRectF(text_x, outer.center().y() - 13, text_w, 17)
            detail_rect = QRectF(text_x, outer.center().y() + 3, text_w, 14)
            title_color = "#000000" if playing else (COLORS["text_dark"] if not enabled else COLORS["text"])
            painter.setPen(QColor(title_color))
            painter.setFont(QFont("Segoe UI", 8 if compact else 9, QFont.Weight.DemiBold))
            fm = painter.fontMetrics()
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(title, Qt.TextElideMode.ElideRight, int(text_w)))
            painter.setPen(QColor(detail_color))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8, QFont.Weight.DemiBold if image_match_state else QFont.Weight.Normal))
            fm = painter.fontMetrics()
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(detail, Qt.TextElideMode.ElideRight, int(text_w)))

            if kind == "group":
                badge = group_badge.get("badge", "F") if group_badge else "F"
                gcol = QColor(group_badge.get("color") if group_badge else type_color)
                chip_w = max(24 if compact else 26, min(icon_rect.width(), 30))
                chip_rect = QRectF(icon_rect.center().x() - chip_w / 2, min(outer.bottom() - 15, icon_rect.bottom() + 1), chip_w, 12)
                self._rounded_rect(painter, chip_rect, 3, COLORS["bg"], gcol.name(), 1)
                painter.setPen(gcol)
                painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Black))
                painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, badge)

            if kind == "image":
                # Runtime image result text is drawn on the subtitle line under
                # the row name.  Keep this area for static confidence metadata.

                # Confidence threshold preview for image actions. This is static
                # metadata, while the match-state badge above reflects runtime.
                # It now lives in the status area, directly left of Pending.
                conf = int(round(_safe_float(getattr(action, "similarity", 0.95), 0.95) * 100))
                if not conf_rect.isNull() and conf_rect.right() > text_x + 10:
                    # Plain confidence text only: no chip/background box.
                    painter.setPen(QColor(type_color))
                    painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                    painter.drawText(conf_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"≥ {conf}%")

            if linked_target and kind != "group":
                link_rect = QRectF(text_x, outer.center().y() + 7, 46 if compact else 54, 14)
                self._rounded_rect(painter, link_rect, 4, COLORS["bg"], COLORS.get("accent", type_color), 1)
                painter.setPen(QColor(COLORS.get("accent", type_color)))
                painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                painter.drawText(link_rect, Qt.AlignmentFlag.AlignCenter, "TARGET")

            # Trace rows retain their subtle row tint/border only; the old
            # TRACE text badge was intentionally removed to prevent clutter.

            if not enabled:
                disabled_rect = QRectF(text_x, outer.center().y() + 7, 54 if compact else 64, 14)
                self._rounded_rect(painter, disabled_rect, 4, COLORS["bg"], COLORS["text_dark"], 1)
                painter.setPen(QColor(COLORS["text_dark"]))
                painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                painter.drawText(disabled_rect, Qt.AlignmentFlag.AlignCenter, "DISABLED")

            # Status chip. It keeps a stable right edge and grows left for
            # longer labels such as Completed/Running/Disabled.
            status_rect = QRectF(status_x, outer.center().y() - 15, status_w, 30)
            self._rounded_rect(painter, status_rect, 5, COLORS["bg"], status_col, 1)
            painter.setPen(QColor(status_col))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, status)

            # Duration metadata; fixed-size column before progress rail.
            dur_rect = QRectF(dur_x, outer.top(), duration_w, outer.height())
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8))
            duration_text = view.duration_text(row, action) if hasattr(view, "duration_text") else _duration_text(action)
            painter.drawText(dur_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, duration_text)

            # Per-action progress bar. This is the responsive part of the row.
            bar_y = outer.center().y() - 3
            bar_h = 6 if compact else 7
            track = QRectF(bar_x, bar_y, bar_w, bar_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["lane"]))
            painter.drawRoundedRect(track, bar_h / 2, bar_h / 2)
            if progress > 0:
                fill = QRectF(bar_x, bar_y, bar_w * progress, bar_h)
                fill_grad = QLinearGradient(QPointF(fill.left(), fill.top()), QPointF(fill.right(), fill.top()))
                fill_a = QColor(_mix(type_color, "#ffffff", 0.34)); fill_a.setAlpha(245)
                fill_b = QColor(type_color); fill_b.setAlpha(230)
                fill_c = QColor(_mix(type_color, COLORS["bg"], 0.12)); fill_c.setAlpha(235)
                fill_grad.setColorAt(0.00, fill_a)
                fill_grad.setColorAt(0.48, fill_b)
                fill_grad.setColorAt(1.00, fill_c)
                painter.setBrush(QBrush(fill_grad))
                painter.drawRoundedRect(fill, bar_h / 2, bar_h / 2)
                if playing and fill.width() >= 4:
                    tip_r = 3.8 if compact else 4.6
                    pulse_dot = QColor(_mix(type_color, "#ffffff", 0.45))
                    pulse_dot.setAlpha(int(150 + 80 * _pulse(speed=1.45)))
                    painter.setBrush(pulse_dot)
                    painter.drawEllipse(QRectF(fill.right() - tip_r, fill.center().y() - tip_r, tip_r * 2, tip_r * 2))

            pct = f"{int(round(progress * 100)):d}%"
            pct_x = bar_x + bar_w + 8
            painter.setPen(QColor(COLORS["text_dim"] if progress < 1 else COLORS["text"]))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8, QFont.Weight.DemiBold))
            painter.drawText(QRectF(pct_x, outer.top(), pct_w, outer.height()), Qt.AlignmentFlag.AlignVCenter, pct)

            # Image threshold metadata is drawn as plain text before the status
            # pill; no extra chip is drawn later in the row.

            # Timeline interaction text such as drag/drop feedback is routed to
            # the top-right status pill.  The row keeps only visual targeting
            # feedback (border/tint/insert line) to avoid clutter.

            # Far-right control.  Group rows keep the same hit-test/collapse
            # behavior, but the visual now reads as a clean expand/collapse
            # chevron instead of a generic kebab menu.
            dot_x = outer.right() - (16 if compact else 22)
            if kind == "group":
                chev_col = QColor(COLORS["text_dim"])
                chev_col.setAlpha(230)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(chev_col, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                cy = outer.center().y()
                collapsed = bool(getattr(action, "group_collapsed", False))
                if collapsed:
                    painter.drawLine(QPointF(dot_x - 3, cy - 6), QPointF(dot_x + 4, cy))
                    painter.drawLine(QPointF(dot_x + 4, cy), QPointF(dot_x - 3, cy + 6))
                else:
                    painter.drawLine(QPointF(dot_x - 6, cy + 3), QPointF(dot_x, cy - 3))
                    painter.drawLine(QPointF(dot_x, cy - 3), QPointF(dot_x + 6, cy + 3))
            else:
                painter.setBrush(QColor(COLORS["text_dim"]))
                painter.setPen(Qt.PenStyle.NoPen)
                for dy in (-7, 0, 7):
                    painter.drawEllipse(QRectF(dot_x, outer.center().y() + dy - 1.5, 3, 3))

            insert_row = -1 if getattr(view, "drop_group_row", -1) >= 0 else getattr(view, "drop_insert_row", -1)
            line_y = None
            if insert_row == row:
                line_y = option.rect.top() + 1
            elif insert_row == row + 1 and row == view.model().rowCount() - 1:
                line_y = option.rect.bottom() - 1
            if line_y is not None:
                line_left = outer.left() + 8
                line_right = outer.right() - 8
                accent = QColor(COLORS["accent"])
                glow = QColor(COLORS["accent"])
                glow.setAlpha(85)
                painter.setPen(QPen(glow, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(QPointF(line_left, line_y), QPointF(line_right, line_y))
                painter.setPen(QPen(accent, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(QPointF(line_left, line_y), QPointF(line_right, line_y))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(accent)
                painter.drawEllipse(QRectF(line_left - 4, line_y - 4, 8, 8))
                painter.drawEllipse(QRectF(line_right - 4, line_y - 4, 8, 8))

                tag_rect = QRectF(line_left + 12, line_y - 10, 82, 20)
                painter.setBrush(QColor(0, 10, 18, 224))
                painter.drawRoundedRect(tag_rect, 7, 7)
                painter.setPen(accent)
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Black))
                painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, "INSERT HERE")
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
        if hasattr(view, "is_row_collapsed_hidden") and view.is_row_collapsed_hidden(index.row()):
            return QSize(100, 0)
        if hasattr(view, "is_row_filtered_hidden") and view.is_row_filtered_hidden(index.row()):
            return QSize(100, 0)
        zoom = _safe_float(getattr(view, "zoom", 1.0), 1.0)
        action = index.data(ActionListModel.ActionRole)
        base_height = 58 if getattr(action, "action_type", "") == "group" else (62 if getattr(option.widget, "width", lambda: 999)() < 700 else 70)
        height = max(50 if getattr(action, "action_type", "") == "group" else 56, int(base_height * zoom))
        return QSize(100, height)


class TimelineView(QListView):
    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)
    action_dragged_many = pyqtSignal(list, int)
    action_dropped_into_group = pyqtSignal(int, int)
    action_dropped_many_into_group = pyqtSignal(list, int)
    group_toggle_requested = pyqtSignal(int)
    selection_summary_changed = pyqtSignal(list)
    interaction_status_changed = pyqtSignal(str)
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None, model=None):
        super().__init__(parent)

        # The v3 shell has enough vertical room for the more legible reference
        # row scale while preserving Ctrl+wheel zoom.
        self.zoom = 1.0
        self.selected_indices = set()
        self._selection_anchor_row = -1
        self._modifier_click_row = -1
        self.playing_index = -1
        self.next_index = -1
        self.active_group_id = ""
        self.paused = False
        self.image_states = {}
        self._search = ""
        self._quick_filter = "all"
        self._search_current_row = -1
        self._search_highlight_rows = set()
        self._drag_start_row = -1
        self._drag_allowed = False
        self.drag_source_row = -1
        self.drag_source_rows = []
        self.drop_insert_row = -1
        self.drop_group_row = -1
        self.drop_feedback_label = ""
        self.drop_feedback_kind = ""
        self.drop_feedback_valid = False
        self.hover_row = -1
        self.flash_row = -1
        self.flash_opacity = 0.0
        self.trace_rows = set()
        self.link_source_row = -1
        self.link_target_rows = set()
        self._auto_scroll_direction = 0
        self._last_drag_pos = None
        self._playing_started = 0.0
        self._playing_duration = 0.0
        self._frozen_progress = 0.0

        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(33)
        self._progress_timer.timeout.connect(self.viewport().update)
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(45)
        self._auto_scroll_timer.timeout.connect(self._auto_scroll_tick)
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(35)
        self._flash_timer.timeout.connect(self._fade_drop_flash)

        self.setModel(model or ActionListModel())
        self.setItemDelegate(TimelineDelegate(self))
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setAlternatingRowColors(False)
        self.setUniformItemSizes(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
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

    def set_zoom(self, value, emit=True):
        old = self.zoom
        try:
            zoom = float(value)
        except (TypeError, ValueError):
            zoom = 1.0
        self.zoom = max(0.55, min(1.60, zoom))
        if self.zoom != old:
            self.setUniformItemSizes(False)
            self.doItemsLayout()
            self.setUniformItemSizes(False)
            self.viewport().update()
            if emit:
                self.zoom_changed.emit(float(self.zoom))

    def _actions(self):
        model = self.model()
        return model.actions() if isinstance(model, ActionListModel) and hasattr(model, "actions") else []

    def _group_headers(self):
        headers = []
        actions = self._actions()
        for row, action in enumerate(actions):
            if getattr(action, "action_type", "") == "group":
                gid = getattr(action, "group_id", "") or f"row-{row}"
                color = getattr(action, "group_color", "") or COLORS.get("group", COLORS.get("accent", "#45c8ff"))
                name = getattr(action, "group_name", "") or getattr(action, "label", "") or f"Folder {len(headers) + 1}"
                count = 0
                duration = 0.0
                for child in actions:
                    if child is action or getattr(child, "action_type", "") == "group":
                        continue
                    if getattr(child, "group_id", "") != gid:
                        continue
                    count += 1
                    if not bool(getattr(child, "enabled", True)):
                        continue
                    kind = getattr(child, "action_type", "key") or "key"
                    if kind in {"loop", "condition"}:
                        continue
                    if kind == "image" and _safe_float(getattr(child, "wait_timeout", 0.0), 0.0) > 0:
                        duration += _safe_float(getattr(child, "wait_timeout", 0.0), 0.0)
                    else:
                        duration += _safe_float(getattr(child, "duration", 0.0), 0.0)
                headers.append({
                    "row": row, "action": action, "gid": gid, "color": color,
                    "name": name, "badge": f"F{len(headers) + 1}",
                    "count": count, "duration": duration, "role": getattr(action, "group_role", "normal"),
                })
        return headers

    def group_badge(self, row: int):
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return None
        action = actions[row]
        gid = getattr(action, "group_id", "")
        if not gid and getattr(action, "action_type", "") != "group":
            return None
        for header in self._group_headers():
            if getattr(action, "action_type", "") == "group" and header["row"] == row:
                return header
            if gid and header["gid"] == gid:
                return header
        return None

    def group_header_for_row(self, row: int):
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return None
        action = actions[row]
        gid = getattr(action, "group_id", "")
        if not gid:
            return None
        for i in range(row, -1, -1):
            candidate = actions[i]
            if getattr(candidate, "action_type", "") == "group" and getattr(candidate, "group_id", "") == gid:
                return i, candidate
        return None

    def is_row_collapsed_hidden(self, row: int) -> bool:
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return False
        action = actions[row]
        if getattr(action, "action_type", "") == "group":
            return False
        header = self.group_header_for_row(row)
        return bool(header and getattr(header[1], "group_collapsed", False))

    def sync_selection(self):
        rows = set()
        sel = self.selectionModel()
        if sel is not None:
            rows = {i.row() for i in sel.selectedRows() if i.isValid()}
            if not rows:
                rows = {i.row() for i in sel.selectedIndexes() if i.isValid()}
        self.selected_indices = {r for r in rows if not self.is_row_collapsed_hidden(r)}
        return self.selected_indices

    def selected_rows(self):
        return sorted(int(r) for r in self.sync_selection())

    def multi_selection_visual_state(self, row: int):
        try:
            row = int(row)
        except (TypeError, ValueError):
            return {"active": False, "count": 0, "has_previous": False, "has_next": False, "ordinal": -1}
        rows = sorted({int(r) for r in getattr(self, "selected_indices", set())})
        if len(rows) <= 1 or row not in rows:
            return {"active": False, "count": len(rows), "has_previous": False, "has_next": False, "ordinal": -1}
        return {
            "active": True,
            "count": len(rows),
            "has_previous": row - 1 in rows,
            "has_next": row + 1 in rows,
            "ordinal": rows.index(row),
        }

    def _is_row_selectable(self, row: int) -> bool:
        if self.model() is None or row < 0 or row >= self.model().rowCount():
            return False
        if self.is_row_collapsed_hidden(row):
            return False
        if hasattr(self, "is_row_filtered_hidden") and self.is_row_filtered_hidden(row):
            return False
        return True

    def _visible_range_rows(self, first: int, last: int):
        lo, hi = sorted((int(first), int(last)))
        return [r for r in range(lo, hi + 1) if self._is_row_selectable(r)]

    def _contiguous_group_block_rows(self, header_row: int):
        actions = self._actions()
        if header_row < 0 or header_row >= len(actions):
            return []
        header = actions[header_row]
        if getattr(header, "action_type", "") != "group":
            return []
        gid = getattr(header, "group_id", "")
        rows = [header_row]
        for r in range(header_row + 1, len(actions)):
            action = actions[r]
            if getattr(action, "action_type", "") == "group":
                break
            if gid and getattr(action, "group_id", "") == gid:
                rows.append(r)
                continue
            break
        return rows

    def expand_rows_for_group_blocks(self, rows):
        """Expand selected folder headers into their contiguous child blocks.

        This keeps timeline block drags safe: dragging a selected folder header
        moves the folder and its visible/hidden children together, while normal
        action-only selections continue to move only those selected actions.
        """
        count = self.model().rowCount() if self.model() is not None else 0
        expanded = set()
        for raw in sorted({int(r) for r in (rows or []) if 0 <= int(r) < count}):
            if self._row_kind(raw) == "group":
                expanded.update(self._contiguous_group_block_rows(raw) or [raw])
            elif not self.is_row_collapsed_hidden(raw):
                expanded.add(raw)
        return sorted(r for r in expanded if 0 <= r < count)

    def drag_rows(self):
        rows = list(getattr(self, "drag_source_rows", []) or [])
        if not rows and self.drag_source_row >= 0:
            rows = [self.drag_source_row]
        return self.expand_rows_for_group_blocks(rows)

    def set_selected_rows(self, rows, active=None):
        rows = sorted({int(r) for r in (rows or []) if self.model() is not None and 0 <= int(r) < self.model().rowCount()})
        self.clearSelection()
        self.selected_indices = set(rows)
        sel = self.selectionModel()
        if sel is not None:
            for row in rows:
                idx = self.model().index(row, 0)
                sel.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        if rows:
            active = rows[0] if active is None or int(active) not in rows else int(active)
            self._selection_anchor_row = int(active)
            active_idx = self.model().index(active, 0)
            if sel is not None:
                sel.setCurrentIndex(active_idx, QItemSelectionModel.SelectionFlag.NoUpdate)
            else:
                self.setCurrentIndex(active_idx)
        else:
            self._selection_anchor_row = -1
            self.setCurrentIndex(QModelIndex())
        self.viewport().update()
        try:
            self.selection_summary_changed.emit(list(rows))
        except Exception:
            pass
        return rows

    def clear_trace(self):
        self.trace_rows.clear()
        self.viewport().update()

    def mark_trace(self, row: int):
        if 0 <= row < self.model().rowCount():
            self.trace_rows.add(row)
            # Keep the trail useful but bounded for large macros.
            if len(self.trace_rows) > 256:
                self.trace_rows = set(sorted(self.trace_rows)[-256:])
            self.viewport().update()

    def set_link_targets(self, source: int = -1, targets=None):
        self.link_source_row = _safe_int(source, -1)
        self.link_target_rows = {
            parsed for parsed in (_safe_int(t, -1) for t in (targets or [])) if parsed >= 0
        }
        self.viewport().update()

    def clear_runtime_visuals(self, clear_playing: bool = False):
        """Reset transient playback visuals without touching macro/action data."""
        if clear_playing:
            self.clear_playing()
        self.image_states.clear()
        self.trace_rows.clear()
        self.link_source_row = -1
        self.link_target_rows.clear()
        self.flash_row = -1
        self.flash_opacity = 0.0
        self.active_group_id = ""
        self.viewport().update()

    def group_progress(self, row: int):
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return {"active": False, "done": 0, "total": 0, "progress": 0.0, "current": ""}
        header = actions[row]
        if getattr(header, "action_type", "") != "group":
            return {"active": False, "done": 0, "total": 0, "progress": 0.0, "current": ""}
        gid = getattr(header, "group_id", "")
        child_rows = [
            i for i, a in enumerate(actions)
            if i != row and getattr(a, "group_id", "") == gid and getattr(a, "action_type", "") != "group"
        ]
        runnable = [i for i in child_rows if bool(getattr(actions[i], "enabled", True)) and getattr(actions[i], "action_type", "key") != "group"]
        total = len(runnable)
        active = self.active_group_id and self.active_group_id == gid
        done = len([i for i in runnable if i in self.trace_rows])
        current = ""
        if self.playing_index in runnable:
            active = True
            done = max(done, len([i for i in runnable if i < self.playing_index]))
            action = actions[self.playing_index]
            current = getattr(action, "label", "") or getattr(action, "key", "") or getattr(action, "action_type", "Action")
        progress = (done / total) if total else 0.0
        if active and self.playing_index in runnable and total:
            progress = max(progress, min(1.0, (done + self.action_progress(self.playing_index)) / total))
        return {"active": bool(active), "done": min(done, total), "total": total, "progress": progress, "current": current}

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

    def duration_text(self, row: int, action) -> str:
        if row != self.playing_index:
            return _duration_text(action)
        remaining = max(0.0, self._playing_duration * (1.0 - self.action_progress(row)))
        return f"{remaining:.1f}s"

    def _timeline_row_rects(self, row: int, visual_rect=None):
        """Return full/card geometry matching TimelineDelegate painting."""
        if row < 0 or self.model() is None or row >= self.model().rowCount():
            return {"full": QRectF(), "card": QRectF(), "compact": False, "child_group": False, "cut": 0}
        rect = visual_rect
        if rect is None:
            idx = self.model().index(row, 0)
            rect = self.visualRect(idx)
        if not rect.isValid():
            return {"full": QRectF(), "card": QRectF(), "compact": False, "child_group": False, "cut": 0}
        narrow = rect.width() < 700
        full = QRectF(rect.adjusted(8, 2, -8, -2) if narrow else rect.adjusted(14, 3, -20, -3))
        compact = full.width() < 760
        actions = self._actions()
        child_group = False
        if 0 <= row < len(actions):
            action = actions[row]
            meta = self.group_badge(row)
            child_group = bool(meta and getattr(action, "action_type", "") != "group")
        cut = (38 if compact else 48) if child_group else 0
        card = QRectF(full)
        if cut:
            card.adjust(cut, 0, 0, 0)
        return {"full": full, "card": card, "compact": compact, "child_group": child_group, "cut": cut}

    def _row_outer_rect(self, row: int):
        """Return the visible painted row card rect used for hit-testing."""
        return self._timeline_row_rects(row).get("card", QRectF())

    def _drag_grip_rect(self, row: int):
        rects = self._timeline_row_rects(row)
        outer = rects.get("card", QRectF())
        if outer.isNull():
            return QRectF()
        compact = bool(rects.get("compact", False))
        stripe_x = outer.left()
        grip_x = stripe_x + 3.0 + (8 if compact else 10) if rects.get("child_group", False) else outer.left() + (12 if compact else 16)
        grip_y = outer.center().y() - 14
        return QRectF(grip_x - 4, grip_y, 24, 28)

    def _kebab_rect(self, row: int):
        outer = self._row_outer_rect(row)
        if outer.isNull():
            return QRectF()
        compact = outer.width() < 760
        dot_x = outer.right() - (16 if compact else 22)
        return QRectF(dot_x - 10, outer.center().y() - 18, 24, 36)

    def _is_drag_grip_hit(self, row: int, pos) -> bool:
        return row >= 0 and self._drag_grip_rect(row).contains(QPointF(pos))

    def _is_kebab_hit(self, row: int, pos) -> bool:
        return row >= 0 and self._kebab_rect(row).contains(QPointF(pos))

    def _row_kind(self, row: int) -> str:
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return ""
        return getattr(actions[row], "action_type", "") or "key"

    def _on_current_changed(self, current, previous):
        self.sync_selection()
        if current.isValid() and self.is_row_collapsed_hidden(current.row()):
            header = self.group_header_for_row(current.row())
            if header:
                self.setCurrentIndex(self.model().index(header[0], 0))
        self.viewport().update()

    def _on_clicked(self, index):
        if index.isValid():
            if int(getattr(self, "_modifier_click_row", -1)) == index.row():
                self._modifier_click_row = -1
                return
            self.sync_selection()
            if not self.selected_indices:
                self.selected_indices = {index.row()}
            self._selection_anchor_row = index.row()
            try:
                self.selection_summary_changed.emit(self.selected_rows())
            except Exception:
                pass
            self.action_clicked.emit(index.row())

    def _on_double_clicked(self, index):
        if index.isValid():
            self.action_double_clicked.emit(index.row())

    def _on_context_menu(self, pos):
        index = self.indexAt(pos)
        row = index.row() if index.isValid() else -1
        self.action_context_menu.emit(row, self.viewport().mapToGlobal(pos))

    def _apply_modifier_click_selection(self, row: int, modifiers) -> bool:
        if row < 0 or self.model() is None or not self._is_row_selectable(row):
            return False
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if not (ctrl or shift):
            return False

        if shift:
            anchor = self._selection_anchor_row
            if anchor < 0 or anchor >= self.model().rowCount() or not self._is_row_selectable(anchor):
                anchor = row
            rows = self._visible_range_rows(anchor, row)
            if ctrl:
                rows = sorted(set(self.selected_indices).union(rows))
            active = row
        else:
            rows = set(self.sync_selection())
            if row in rows:
                rows.remove(row)
            else:
                rows.add(row)
            rows = sorted(r for r in rows if self._is_row_selectable(r))
            active = row if row in rows else (rows[-1] if rows else -1)
            self._selection_anchor_row = row

        self.set_selected_rows(rows, active=active if active >= 0 else None)
        self._modifier_click_row = row
        if active >= 0:
            self.action_clicked.emit(active)
        else:
            self.action_clicked.emit(-1)
        return True

    def mousePressEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        idx = self.indexAt(pos)
        row = idx.row() if idx.isValid() else -1
        self._drag_start_row = -1
        self._drag_allowed = False

        if idx.isValid() and self.is_row_collapsed_hidden(row):
            header = self.group_header_for_row(row)
            if header:
                row = header[0]
                idx = self.model().index(row, 0)

        # Left-clicking the far-right kebab on a group row is the only direct
        # collapse/expand gesture. Other clicks select rows only.
        if event.button() == Qt.MouseButton.LeftButton and not idx.isValid():
            # Empty timeline space is a deliberate deselect gesture.
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
            self.selected_indices.clear()
            self._selection_anchor_row = -1
            try:
                self.selection_summary_changed.emit([])
            except Exception:
                pass
            self.action_clicked.emit(-1)
            self.viewport().update()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and idx.isValid():
            if self._row_kind(row) == "group" and self._is_kebab_hit(row, pos):
                self.group_toggle_requested.emit(row)
                event.accept()
                return
            if self._apply_modifier_click_selection(row, event.modifiers()):
                event.accept()
                return
            if self._is_drag_grip_hit(row, pos) and self.playing_index < 0:
                self._drag_start_row = row
                self._drag_allowed = True
                self.setDragEnabled(True)
            else:
                # Dragging is deliberately disabled unless the press began on
                # the far-left grid dots. This keeps selection/collapse stable.
                self.setDragEnabled(False)

        if event.button() == Qt.MouseButton.RightButton and idx.isValid() and row in self.selected_indices:
            return
        super().mousePressEvent(event)
        self.sync_selection()
        if idx.isValid() and event.button() == Qt.MouseButton.LeftButton:
            self._selection_anchor_row = row
            try:
                self.selection_summary_changed.emit(self.selected_rows())
            except Exception:
                pass

    def paintEvent(self, event):
        # Row/insert/drop visuals are handled by the delegate.  Timeline
        # interaction status text is emitted to the top-right status pill so no
        # floating overlay competes with the clean timeline rows.
        super().paintEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(pos)
        self.hover_row = index.row() if index.isValid() else -1
        if index.isValid():
            row = index.row()
            if self._is_drag_grip_hit(row, pos) and self.playing_index < 0:
                self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            elif self._row_kind(row) == "group" and self._is_kebab_hit(row, pos):
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.viewport().unsetCursor()
        else:
            self.viewport().unsetCursor()
        self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hover_row = -1
        if self.drag_source_row < 0:
            self.viewport().unsetCursor()
        self.viewport().update()
        super().leaveEvent(event)

    def startDrag(self, supported_actions):
        if self.playing_index >= 0 or not self._drag_allowed or self._drag_start_row < 0:
            return
        selected = self.selected_rows()
        if self._drag_start_row in selected and len(selected) > 1:
            self.drag_source_rows = self.expand_rows_for_group_blocks(selected)
        else:
            self.drag_source_rows = self.expand_rows_for_group_blocks([self._drag_start_row])
        if set(self.drag_source_rows) != set(selected):
            self.set_selected_rows(self.drag_source_rows, active=self._drag_start_row)
        self.drag_source_row = self._drag_start_row
        try:
            count = len(self.drag_rows())
            self._emit_interaction_status(f"Dragging {count} row{'s' if count != 1 else ''}")
        except Exception:
            pass
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        self.viewport().update()
        try:
            super().startDrag(supported_actions)
        finally:
            self._stop_drag_feedback()

    def dragEnterEvent(self, event):
        if event.source() is self:
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def _emit_interaction_status(self, text: str):
        try:
            msg = str(text or "")
            if msg:
                self.interaction_status_changed.emit(msg)
        except Exception:
            pass

    def dragMoveEvent(self, event):
        if event.source() is self:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self._last_drag_pos = pos
            self._update_auto_scroll(pos)
            invalid_row = self._invalid_group_nest_row(pos)
            if invalid_row >= 0:
                self.drop_group_row = invalid_row
                self.drop_insert_row = -1
                self.drop_feedback_kind = "invalid"
                self.drop_feedback_valid = False
                self.drop_feedback_label = "Folders cannot be nested"
                self.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
            else:
                self.viewport().unsetCursor()
                group_row = self._drop_group_row(pos)
                if group_row >= 0:
                    self.drop_group_row = group_row
                    self.drop_insert_row = -1
                    self.drop_feedback_kind = "group"
                    self.drop_feedback_valid = True
                    drag_count = len(self.drag_rows())
                    base_label = self.drop_feedback_text(group_row)
                    self.drop_feedback_label = f"Drop {drag_count} actions into folder" if drag_count > 1 else base_label
                else:
                    self.drop_group_row = -1
                    self.drop_insert_row = self._drop_insert_row(pos)
                    self.drop_feedback_kind = "insert"
                    self.drop_feedback_valid = self.drop_insert_row >= 0
                    if self.drop_feedback_valid:
                        drag_count = len(self.drag_rows())
                        self.drop_feedback_label = (
                            f"Move {drag_count} actions to row {self.drop_insert_row + 1}"
                            if drag_count > 1 else f"Move to row {self.drop_insert_row + 1}"
                        )
                    else:
                        self.drop_feedback_label = "Drop unavailable"
            self._emit_interaction_status(self.drop_feedback_label)
            self.viewport().update()
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._stop_auto_scroll()
        super().dragLeaveEvent(event)

    def _update_auto_scroll(self, pos):
        margin = min(42, max(24, self.viewport().height() // 8))
        if pos.y() < margin:
            self._auto_scroll_direction = -1
        elif pos.y() > self.viewport().height() - margin:
            self._auto_scroll_direction = 1
        else:
            self._auto_scroll_direction = 0
        if self._auto_scroll_direction and not self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.start()
        elif not self._auto_scroll_direction:
            self._auto_scroll_timer.stop()

    def _auto_scroll_tick(self):
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + (18 * self._auto_scroll_direction))
        if self._last_drag_pos is not None:
            invalid_row = self._invalid_group_nest_row(self._last_drag_pos)
            if invalid_row >= 0:
                self.drop_group_row = invalid_row
                self.drop_insert_row = -1
                self.drop_feedback_kind = "invalid"
                self.drop_feedback_valid = False
                self.drop_feedback_label = "Folders cannot be nested"
                self.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
            else:
                self.viewport().unsetCursor()
                group_row = self._drop_group_row(self._last_drag_pos)
                if group_row >= 0:
                    self.drop_group_row = group_row
                    self.drop_insert_row = -1
                    self.drop_feedback_kind = "group"
                    self.drop_feedback_valid = True
                    drag_count = len(self.drag_rows())
                    base_label = self.drop_feedback_text(group_row)
                    self.drop_feedback_label = f"Drop {drag_count} actions into folder" if drag_count > 1 else base_label
                else:
                    self.drop_group_row = -1
                    self.drop_insert_row = self._drop_insert_row(self._last_drag_pos)
                    self.drop_feedback_kind = "insert"
                    self.drop_feedback_valid = self.drop_insert_row >= 0
                    if self.drop_feedback_valid:
                        drag_count = len(self.drag_rows())
                        self.drop_feedback_label = (
                            f"Move {drag_count} actions to row {self.drop_insert_row + 1}"
                            if drag_count > 1 else f"Move to row {self.drop_insert_row + 1}"
                        )
                    else:
                        self.drop_feedback_label = "Drop unavailable"
            self._emit_interaction_status(self.drop_feedback_label)
            self.viewport().update()

    def _stop_auto_scroll(self):
        self._auto_scroll_direction = 0
        self._auto_scroll_timer.stop()

    def _stop_drag_feedback(self):
        self._stop_auto_scroll()
        self._drag_start_row = -1
        self._drag_allowed = False
        self.drag_source_row = -1
        self.drag_source_rows = []
        self.drop_insert_row = -1
        self.drop_group_row = -1
        self.drop_feedback_label = ""
        self.drop_feedback_kind = ""
        self.drop_feedback_valid = False
        self._last_drag_pos = None
        self.setDragEnabled(False)
        self.viewport().unsetCursor()
        self.viewport().update()

    def flash_drop(self, row: int):
        self.flash_row = row
        self.flash_opacity = 1.0
        self.viewport().update()
        self._flash_timer.start()

    def _fade_drop_flash(self):
        self.flash_opacity = max(0.0, self.flash_opacity - 0.09)
        if self.flash_opacity > 0.0:
            self.viewport().update()
            return
        self._flash_timer.stop()
        self.flash_row = -1
        self.viewport().update()

    def _drag_contains_group(self) -> bool:
        return any(self._row_kind(r) == "group" for r in self.drag_rows())

    def _invalid_group_nest_row(self, pos) -> int:
        if self.model() is None or self._drag_start_row < 0 or not self._drag_contains_group():
            return -1
        idx = self.indexAt(pos)
        if not idx.isValid():
            return -1
        row = idx.row()
        if self.is_row_collapsed_hidden(row):
            header = self.group_header_for_row(row)
            if not header:
                return -1
            row = header[0]
            idx = self.model().index(row, 0)
        if row in set(self.drag_rows()) or self._row_kind(row) != "group":
            return -1
        rect = self.visualRect(idx)
        if not rect.isValid() or rect.height() <= 0:
            return -1
        rel_y = (pos.y() - rect.top()) / max(1, rect.height())
        return row if 0.18 <= rel_y <= 0.82 else -1

    def _drop_group_row(self, pos) -> int:
        """Return a folder header row when the cursor is in its central drop zone.

        Top/bottom edges still behave like normal reorder insertion targets, so
        users can move rows around a folder without accidentally adding them to it.
        """
        if self.model() is None or self._drag_start_row < 0:
            return -1
        if self._invalid_group_nest_row(pos) >= 0:
            return -1
        if self._row_kind(self._drag_start_row) == "group":
            return -1
        idx = self.indexAt(pos)
        if not idx.isValid():
            return -1
        row = idx.row()
        if row == self._drag_start_row:
            return -1
        if self.is_row_collapsed_hidden(row):
            header = self.group_header_for_row(row)
            if not header:
                return -1
            row = header[0]
            idx = self.model().index(row, 0)
        if self._row_kind(row) != "group":
            return -1
        drag_rows = set(self.drag_rows())
        if row in drag_rows:
            return -1
        if any(self._row_kind(r) == "group" for r in drag_rows):
            return -1

        # Use the centre of the header card as the intentional "drop into" zone.
        # Dropping near the top/bottom keeps the existing insert-line behavior.
        rect = self.visualRect(idx)
        if not rect.isValid() or rect.height() <= 0:
            return -1
        rel_y = (pos.y() - rect.top()) / max(1, rect.height())
        if 0.22 <= rel_y <= 0.78:
            return row
        return -1

    def _drop_insert_row(self, pos) -> int:
        count = self.model().rowCount() if self.model() is not None else 0
        if count <= 0:
            return -1
        target_index = self.indexAt(pos)
        if not target_index.isValid():
            return count
        target = target_index.row()
        if pos.y() > self.visualRect(target_index).center().y():
            target += 1
        return max(0, min(target, count))

    def _drop_target_row(self, pos) -> int:
        count = self.model().rowCount() if self.model() is not None else 0
        if count <= 0:
            return -1
        target = self._drop_insert_row(pos)
        if self._drag_start_row < target:
            target -= 1
        return max(0, min(target, count - 1))

    def dropEvent(self, event):
        source = self._drag_start_row
        rows = self.drag_rows()
        if self.playing_index >= 0 or not self._drag_allowed:
            event.ignore()
            self._stop_drag_feedback()
            return
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        invalid_row = self._invalid_group_nest_row(pos)
        if invalid_row >= 0:
            self._stop_auto_scroll()
            self.drop_group_row = invalid_row
            self.drop_insert_row = -1
            self.drop_feedback_kind = "invalid"
            self.drop_feedback_valid = False
            self.drop_feedback_label = "Folders cannot be nested"
            self._emit_interaction_status(self.drop_feedback_label)
            self.flash_drop(invalid_row)
            event.acceptProposedAction()
            QTimer.singleShot(120, self._stop_drag_feedback)
            return
        group_target = self._drop_group_row(pos)
        target = self._drop_insert_row(pos) if group_target < 0 else -1
        single_target = self._drop_target_row(pos) if group_target < 0 else -1
        self._stop_auto_scroll()
        event.acceptProposedAction()
        if source >= 0 and group_target >= 0:
            self.flash_drop(group_target)
            if len(rows) > 1:
                QTimer.singleShot(0, lambda r=rows, g=group_target: self.action_dropped_many_into_group.emit(r, g))
            else:
                QTimer.singleShot(0, lambda s=source, g=group_target: self.action_dropped_into_group.emit(s, g))
        elif source >= 0 and target >= 0:
            flash_target = target if len(rows) > 1 else single_target
            if len(rows) > 1:
                self.flash_drop(max(0, min(flash_target, self.model().rowCount() - 1)))
                QTimer.singleShot(0, lambda r=rows, t=target: self.action_dragged_many.emit(r, t))
            elif single_target >= 0 and source != single_target:
                self.flash_drop(single_target)
                QTimer.singleShot(0, lambda s=source, t=single_target: self.action_dragged.emit(s, t))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            self.set_zoom(self.zoom * (1.08 if delta > 0 else 1 / 1.08))
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
        self._selection_anchor_row = -1
        self.viewport().update()

    def set_active(self, index):
        if index is not None and 0 <= index < self.model().rowCount():
            idx = self.model().index(index, 0)
            self.clearSelection()
            self.setCurrentIndex(idx)
            sel = self.selectionModel()
            if sel is not None:
                sel.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            self.selected_indices = {index}
            self._selection_anchor_row = index
        else:
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
            self.selected_indices.clear()
            self._selection_anchor_row = -1
        self.viewport().update()
        try:
            self.selection_summary_changed.emit(sorted(self.selected_indices))
        except Exception:
            pass

    def set_playing(self, index, duration=0.0):
        self.playing_index = index
        self.next_index = index + 1 if index + 1 < self.model().rowCount() else -1
        self.active_group_id = ""
        try:
            header = self.group_header_for_row(index)
            if header:
                self.active_group_id = getattr(header[1], "group_id", "")
        except Exception:
            self.active_group_id = ""
        self.paused = False
        self._playing_duration = max(0.0, _safe_float(duration, 0.0))
        self._playing_started = time.monotonic()
        self._frozen_progress = 0.0
        self.setDragEnabled(False)
        self._stop_drag_feedback()
        if 0 <= index < self.model().rowCount():
            self.scrollTo(self.model().index(index, 0), QAbstractItemView.ScrollHint.EnsureVisible)
        if not self._progress_timer.isActive():
            self._progress_timer.start()
        self.viewport().update()

    def clear_playing(self):
        self.playing_index = -1
        self.next_index = -1
        self.active_group_id = ""
        self.paused = False
        self._frozen_progress = 0.0
        self.setDragEnabled(False)
        if self._progress_timer.isActive():
            self._progress_timer.stop()
        self.viewport().update()

    def clear_image_states(self):
        self.image_states.clear()
        self.viewport().update()

    def set_image_state(self, index, state):
        if 0 <= index < self.model().rowCount():
            self.image_states[index] = state
            self.viewport().update()

    def remap_after_move(self, source: int, target: int):
        if source == target:
            return

        def remap(row):
            if row == source:
                return target
            if source < target and source < row <= target:
                return row - 1
            if target < source and target <= row < source:
                return row + 1
            return row

        self.image_states = {remap(row): state for row, state in self.image_states.items()}
        if self.playing_index >= 0:
            self.playing_index = remap(self.playing_index)
        if self.next_index >= 0:
            self.next_index = remap(self.next_index)
        self.viewport().update()

    def scroll_position(self) -> int:
        return self.verticalScrollBar().value()

    def restore_scroll_position(self, value: int):
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(max(scrollbar.minimum(), min(int(value or 0), scrollbar.maximum())))

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

    def ensure_visible_if_needed(self, index):
        if index < 0 or index >= self.model().rowCount():
            return
        rect = self.visualRect(self.model().index(index, 0))
        if not self.viewport().rect().contains(rect):
            self.ensure_visible(index)

    def set_quick_filter(self, value: str):
        """Apply the toolbar mode filter and keep search navigation stable."""
        self._quick_filter = (value or "all").strip().lower().replace("_", " ")
        self._search_current_row = -1
        matches = self.search_match_rows()
        if matches and (self._search or self._quick_filter not in {"", "all"}):
            self._search_current_row = matches[0] if self._search else -1
            if self._search:
                self.set_active(matches[0])
                self.ensure_visible(matches[0])
        self.doItemsLayout()
        self.viewport().update()

    def _searchable_text_for_row(self, row: int) -> str:
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return ""
        action = actions[row]
        meta = self.group_badge(row)
        kind = getattr(action, "action_type", "key") or "key"
        title, detail = _action_text(action)
        values = [
            str(row + 1), f"row {row + 1}", kind, title, detail,
            getattr(action, "label", ""), getattr(action, "key", ""),
            getattr(action, "group_name", ""), getattr(action, "condition_type", ""),
            getattr(action, "condition_var_name", ""), getattr(action, "condition_var_value", ""),
            getattr(action, "condition_color", ""), getattr(action, "click_button", ""),
            getattr(action, "click_coord_mode", ""), getattr(action, "search_region", ""),
            getattr(action, "fail_mode", ""), getattr(action, "on_fail", ""),
            getattr(action, "action_type", ""),
        ]
        for attr in (
            "click_x", "click_y", "click_rand_radius", "duration", "repeat_count",
            "loop_count", "loop_target", "wait_timeout", "similarity",
            "retry_count", "retry_delay", "condition_x", "condition_y",
            "condition_jump_true", "condition_jump_false", "fail_target",
        ):
            try:
                values.append(str(getattr(action, attr, "")))
            except Exception:
                pass
        if meta:
            values.extend([meta.get("badge", ""), meta.get("name", ""), meta.get("role", "")])
        if not bool(getattr(action, "enabled", True)):
            values.extend(["disabled", "off"])
        if kind == "image" and not getattr(action, "image_data", ""):
            values.extend(["warning", "missing", "template"])
        return " ".join(str(v or "") for v in values).lower()

    def _row_matches_search(self, row: int) -> bool:
        query = (self._search or "").strip().lower()
        if not query:
            return True
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return False
        action = actions[row]
        meta = self.group_badge(row)
        kind = getattr(action, "action_type", "key") or "key"
        haystack = self._searchable_text_for_row(row)
        tokens = [t for t in query.replace(",", " ").split() if t]
        for token in tokens:
            if ":" in token:
                field, value = token.split(":", 1)
                field = field.strip().lower()
                value = value.strip().lower()
                if not value:
                    continue
                if field in {"type", "kind", "action"}:
                    if kind != value:
                        return False
                    continue
                if field in {"label", "name"}:
                    if value not in str(getattr(action, "label", "")).lower() and value not in str(getattr(action, "group_name", "")).lower():
                        return False
                    continue
                if field == "group":
                    g = ((meta.get("badge", "") + " " + meta.get("name", "")) if meta else "").lower()
                    if value not in g:
                        return False
                    continue
                if field in {"status", "state"}:
                    if value in {"disabled", "off"} and bool(getattr(action, "enabled", True)):
                        return False
                    if value in {"enabled", "on"} and not bool(getattr(action, "enabled", True)):
                        return False
                    if value in {"warn", "warning", "missing", "error"} and not self._row_has_warning(row):
                        return False
                    continue
                if field == "key" and value not in str(getattr(action, "key", "")).lower():
                    return False
                if field in {"row", "#"} and value != str(row + 1):
                    return False
                if field in {"image", "template"}:
                    if kind != "image" or value not in haystack:
                        return False
                    continue
                if f"{field}:{value}" not in haystack and value not in haystack:
                    return False
            elif token not in haystack:
                return False
        return True

    def _row_has_warning(self, row: int) -> bool:
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return False
        action = actions[row]
        kind = getattr(action, "action_type", "key") or "key"
        if not bool(getattr(action, "enabled", True)):
            return True
        if kind == "image" and not getattr(action, "image_data", ""):
            return True
        if kind == "loop" and _safe_int(getattr(action, "loop_target", -1), -1) < 0:
            return True
        if kind == "condition":
            ctype = getattr(action, "condition_type", "none") or "none"
            if ctype in {"", "none"}:
                return True
        return False

    def _row_matches_quick_filter(self, row: int) -> bool:
        filt = (self._quick_filter or "all").lower().replace("_", " ")
        if filt in {"", "all", "all actions"}:
            return True
        actions = self._actions()
        if row < 0 or row >= len(actions):
            return False
        action = actions[row]
        kind = getattr(action, "action_type", "key") or "key"
        aliases = {
            "key actions": "key", "keys": "key",
            "click actions": "click", "clicks": "click",
            "delay actions": "delay", "delays": "delay", "pause": "pause", "pauses": "pause",
            "image actions": "image", "images": "image",
            "condition actions": "condition", "conditions": "condition",
            "loop actions": "loop", "loops": "loop",
            "folder headers": "group", "folders": "group", "group headers": "group", "groups": "group",
        }
        target = aliases.get(filt, filt)
        if target == "delay":
            return kind in {"pause", "delay"} or getattr(action, "key", "") in {"[PAUSE]", "[DELAY]"}
        if target in {"key", "click", "image", "condition", "loop", "group", "pause"}:
            return kind == target
        if filt == "selected":
            return row in getattr(self, "selected_indices", set())
        if filt == "disabled":
            return not bool(getattr(action, "enabled", True))
        if filt in {"warnings", "warnings / missing data", "missing", "errors"}:
            return self._row_has_warning(row)
        if filt == "current group":
            target_gid = self.active_group_id
            target_header_row = -1
            if not target_gid:
                try:
                    active = self.currentIndex().row() if self.currentIndex().isValid() else -1
                except Exception:
                    active = -1
                meta = self.group_badge(active) if active >= 0 else None
                if meta:
                    target_gid = meta.get("gid", "")
                    target_header_row = int(meta.get("row", -1))
            if not target_gid:
                return True
            return getattr(action, "group_id", "") == target_gid or row == target_header_row
        return True

    def is_row_filtered_hidden(self, row: int) -> bool:
        return not (self._row_matches_search(row) and self._row_matches_quick_filter(row))

    def visible_match_rows(self):
        return [
            row for row in range(self.model().rowCount())
            if not self.is_row_collapsed_hidden(row) and not self.is_row_filtered_hidden(row)
        ]

    def search_match_rows(self):
        # When a text search is active, this means actual text-search matches
        # after the current mode filter.  With no text, it returns the rows
        # visible under the current mode filter so the toolbar can show counts.
        return self.visible_match_rows()

    def current_search_match_position(self):
        rows = self.search_match_rows()
        if not rows:
            return 0, 0
        current = self._search_current_row if self._search_current_row in rows else rows[0]
        return rows.index(current) + 1, len(rows)

    def jump_to_search_match(self, direction=1):
        rows = self.search_match_rows()
        if not rows:
            self._search_current_row = -1
            self.viewport().update()
            return -1
        direction = -1 if int(direction or 1) < 0 else 1
        current = self._search_current_row
        if current not in rows:
            try:
                active = int(getattr(self, "active_index", -1))
            except Exception:
                active = -1
            if active in rows:
                current = active
            else:
                current = rows[-1] if direction < 0 else rows[0]
                self._search_current_row = current
                self.set_active(current)
                self.ensure_visible(current)
                self.viewport().update()
                return current
        idx = rows.index(current)
        idx = (idx + direction) % len(rows)
        row = rows[idx]
        self._search_current_row = row
        self.set_active(row)
        self.ensure_visible(row)
        self.viewport().update()
        return row

    def drop_feedback_text(self, row: int) -> str:
        meta = self.group_badge(row)
        if meta:
            return f"Add to {meta.get('badge', 'G')}"
        return "Add to folder"

    def set_search(self, text: str):
        self._search = (text or "").strip().lower()
        rows = self.search_match_rows()
        if self._search:
            self._search_highlight_rows = set(rows)
        first = rows[0] if rows else -1
        self._search_current_row = first if self._search and first >= 0 else -1
        if first >= 0 and self._search:
            self.set_active(first)
            self.ensure_visible(first)
        self.doItemsLayout()
        self.viewport().update()

    def refresh(self):
        self.doItemsLayout()
        self.viewport().update()
