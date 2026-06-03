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
        return title, f"Repeat x{repeat}" if repeat > 1 else ""

    if kind == "click":
        button = (getattr(action, "click_button", "left") or "left").title()
        mode = getattr(action, "click_coord_mode", "absolute") or "absolute"
        x, y = getattr(action, "click_x", 0), getattr(action, "click_y", 0)
        rand = int(getattr(action, "click_rand_radius", 0) or 0)
        rand_txt = f" · ±{rand}px" if rand > 0 else ""
        return label or f"{button} Click", f"{mode.title()} · X {x}, Y {y}{rand_txt}{repeat_txt}"

    if kind == "image":
        conf = float(getattr(action, "similarity", 0.95) or 0.95) * 100
        timeout = float(getattr(action, "wait_timeout", 0.0) or 0.0)
        detail = f"Template.png · confidence ≥ {conf:.0f}%"
        if timeout > 0:
            detail += f" · wait {timeout:.1f}s"
        return label or "Image", detail

    if kind == "group":
        name = getattr(action, "group_name", "") or label or "Group"
        collapsed = "Collapsed" if bool(getattr(action, "group_collapsed", False)) else "Folder"
        return name, collapsed

    if kind == "loop":
        count = int(getattr(action, "loop_count", getattr(action, "repeat_count", 2)) or 2)
        target = int(getattr(action, "loop_target", -1) or -1)
        detail = f"Repeat x{count}"
        if target >= 0:
            detail += f" · back to row {target + 1}"
        return label or "Loop block", detail

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

    def paint(self, painter: QPainter, option, index):
        painter.save()
        try:
            view = option.widget
            row = index.row()
            if hasattr(view, "is_row_collapsed_hidden") and view.is_row_collapsed_hidden(row):
                return
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            action = index.data(ActionListModel.ActionRole)
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            hovered = row == getattr(view, "hover_row", -1)
            playing = row == getattr(view, "playing_index", -1)
            queued = row == getattr(view, "next_index", -1)
            dragging = row == getattr(view, "drag_source_row", -1)
            group_drop_target = row == getattr(view, "drop_group_row", -1)
            flashed = row == getattr(view, "flash_row", -1)
            flash_opacity = float(getattr(view, "flash_opacity", 0.0) or 0.0)
            traced = row in getattr(view, "trace_rows", set())
            linked_source = row == getattr(view, "link_source_row", -1)
            linked_target = row in getattr(view, "link_target_rows", set())
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

            narrow = option.rect.width() < 700
            # Compact timeline treatment: tighter outer padding keeps more rows
            # visible at once without changing the overall layout structure.
            outer = option.rect.adjusted(8, 2, -8, -2) if narrow else option.rect.adjusted(14, 3, -20, -3)
            bg = COLORS["bg_card"]
            if not enabled:
                bg = _mix(bg, COLORS["bg"], 0.72)
            if hovered:
                bg = _mix(bg, COLORS["bg_hover"], 0.5)
            if selected and hovered:
                bg = _mix(bg, type_color, 0.12)
            if queued or active_group:
                bg = _mix(bg, type_color, 0.07 if queued else 0.10)
            if dragging:
                bg = _mix(bg, type_color, 0.18)
                outer.translate(0, -2)
            if traced and not playing:
                bg = _mix(bg, COLORS.get("success", type_color), 0.07)
            if linked_source and not playing:
                bg = _mix(bg, type_color, 0.10)
            if linked_target and not playing:
                bg = _mix(bg, COLORS.get("accent", type_color), 0.13)
            if group_drop_target and kind == "group" and not playing:
                bg = _mix(bg, COLORS.get("success", type_color), 0.18)
            if flashed:
                bg = _mix(bg, type_color, 0.22 * flash_opacity)

            border = COLORS["border"]
            if selected and hovered:
                border = COLORS["border_light"]
            if queued:
                border = _mix(COLORS["border"], type_color, 0.35)
            if traced:
                border = _mix(COLORS["border"], COLORS.get("success", type_color), 0.34)
            if linked_source:
                border = _mix(COLORS["border_light"], type_color, 0.55)
            if linked_target:
                border = COLORS.get("accent", type_color)
            if group_drop_target and kind == "group":
                border = COLORS.get("success", type_color)
            if dragging or flashed:
                border = _mix(COLORS["border_light"], type_color, 0.55)
            if playing:
                border = type_color

            if kind == "group" and not playing:
                bg = _mix(COLORS["bg_card"], type_color, 0.14)
                border = _mix(COLORS["border_light"], type_color, 0.45)

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
                if dragging:
                    shadow = QRectF(outer)
                    shadow.translate(0, 4)
                    shadow_col = QColor("#000000")
                    shadow_col.setAlpha(95)
                    self._rounded_rect(painter, shadow, 8, shadow_col.name(QColor.NameFormat.HexArgb))
                self._rounded_rect(painter, outer, 8, bg, border, 1)

            # Compact-aware layout. Timeline metadata stays visible at every
            # supported window size; only the progress rail flexes horizontally.
            compact = outer.width() < 760

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

            if group_badge and kind != "group":
                rail = QRectF(outer.left() + 5, outer.top() + 5, 2.0, outer.height() - 10)
                rail_col = QColor(group_badge.get("color") or type_color)
                rail_col.setAlpha(150)
                painter.setBrush(rail_col)
                painter.drawRoundedRect(rail, 1, 1)

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
            grip_color = "#000000" if playing else (COLORS["border_light"] if getattr(view, "playing_index", -1) >= 0 else COLORS["text_dark"])
            painter.setBrush(QColor(grip_color))
            for gx in (0, 5):
                for gy in (0, 5, 10):
                    painter.drawEllipse(QRectF(grip_x + gx, grip_y + gy, 2.0, 2.0))

            # Index.
            num_left = outer.left() + (28 if compact else 46)
            num_rect = QRectF(num_left, outer.top(), 26 if compact else 30, outer.height())
            num_color = "#000000" if playing else COLORS["text"]
            painter.setPen(QColor(num_color))
            painter.setFont(QFont("Segoe UI", 9 if compact else 10, QFont.Weight.DemiBold))
            painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(row + 1))

            if group_badge and kind != "group":
                gb_rect = QRectF(num_rect.left() - 2, outer.center().y() + 9, num_rect.width() + 4, 14)
                gb_col = QColor(group_badge.get("color") or type_color)
                gb_bg = QColor(COLORS["bg"])
                painter.setPen(QPen(gb_col, 1))
                painter.setBrush(QBrush(gb_bg))
                painter.drawRoundedRect(gb_rect, 4, 4)
                painter.setPen(gb_col)
                painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.Black))
                painter.drawText(gb_rect, Qt.AlignmentFlag.AlignCenter, group_badge.get("badge", "G"))

            # Icon tile.
            icon_size = 28 if compact else 34
            icon_left = outer.left() + (54 if compact else 82)
            icon_rect = QRectF(icon_left, outer.center().y() - icon_size / 2, icon_size, icon_size)
            path = QPainterPath(); path.addRoundedRect(icon_rect, 8, 8)
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
            painter.setBrush(QBrush(QColor(COLORS["bg"])))
            painter.drawPath(path)
            self._draw_type_icon(painter, icon_rect, kind, type_color)

            # Right-side progress area. Status and duration are static columns;
            # only the progress rail expands/contracts with window width.
            menu_reserve = 22 if compact else 26
            pct_w = 38 if compact else 44
            right_edge = outer.right() - menu_reserve - pct_w - 10

            status_w = 76 if compact else 92
            status_x = outer.left() + (216 if compact else 300)
            duration_w = 46 if compact else 56
            dur_x = status_x + status_w + 10
            bar_x = dur_x + duration_w + 10
            bar_w = max(28, int(right_edge - bar_x))

            # Title/detail with elision so compact windows remain readable.
            title, detail = _action_text(action)
            if kind == "group" and group_badge:
                count = int(group_badge.get("count", 0) or 0)
                dur = float(group_badge.get("duration", 0.0) or 0.0)
                hidden = " hidden" if bool(getattr(action, "group_collapsed", False)) else ""
                detail = f"{count} action{'s' if count != 1 else ''}{hidden} · ~{dur:.1f}s"
                if hasattr(view, "group_progress"):
                    gp = view.group_progress(row)
                    if gp.get("active") or gp.get("progress", 0) > 0:
                        cur = gp.get("current", "")
                        cur_txt = f" · {cur}" if cur else ""
                        detail = f"{gp.get('done', 0)}/{max(1, gp.get('total', count))} actions · {int(round(gp.get('progress', 0) * 100))}%{cur_txt}"
            if kind == "loop" and hasattr(view, "group_badge"):
                target = int(getattr(action, "loop_target", -1) or -1)
                meta = view.group_badge(target) if target >= 0 else None
                count = int(getattr(action, "loop_count", getattr(action, "repeat_count", 2)) or 2)
                if meta:
                    detail = f"Repeat x{count} · back to {meta.get('badge', 'G')} {meta.get('name', 'Group')}"
            depth = max(0, int(getattr(action, "block_depth", 0) or 0))
            text_x = icon_rect.right() + 14 + min(depth, 4) * 12
            text_right = max(text_x + 72, status_x - 14)
            text_w = max(72, text_right - text_x)
            title_rect = QRectF(text_x, outer.center().y() - 13, text_w, 17)
            detail_rect = QRectF(text_x, outer.center().y() + 3, text_w, 14)
            title_color = "#000000" if playing else (COLORS["text_dark"] if not enabled else COLORS["text"])
            painter.setPen(QColor(title_color))
            painter.setFont(QFont("Segoe UI", 8 if compact else 9, QFont.Weight.DemiBold))
            fm = painter.fontMetrics()
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(title, Qt.TextElideMode.ElideRight, int(text_w)))
            painter.setPen(QColor(COLORS["text_dim"]))
            painter.setFont(QFont("Segoe UI", 7 if compact else 8))
            fm = painter.fontMetrics()
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, fm.elidedText(detail, Qt.TextElideMode.ElideRight, int(text_w)))

            if kind == "group":
                tri = "▶" if bool(getattr(action, "group_collapsed", False)) else "▼"
                badge = group_badge.get("badge", "G") if group_badge else "G"
                gcol = QColor(group_badge.get("color") if group_badge else type_color)
                chip_rect = QRectF(text_x, outer.center().y() + 8, 56 if compact else 66, 16)
                self._rounded_rect(painter, chip_rect, 4, COLORS["bg"], gcol.name(), 1)
                painter.setPen(gcol)
                painter.setFont(QFont("Segoe UI", 7 if compact else 8, QFont.Weight.Black))
                painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, f"{tri} {badge}")

            if kind == "image":
                match_state = getattr(view, "image_states", {}).get(row, "")
                if match_state:
                    match_col = {
                        "Found": COLORS["success"],
                        "Waiting": COLORS["neon_gold"],
                        "Missed": COLORS["error"],
                    }.get(match_state, COLORS["text_dim"])
                    badge_w = 42 if compact else 50
                    badge_rect = QRectF(text_x, outer.center().y() - 7, badge_w, 14)
                    self._rounded_rect(painter, badge_rect, 4, COLORS["bg"], match_col, 1)
                    painter.setPen(QColor(match_col))
                    painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                    painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, match_state)

                # Confidence threshold preview for image actions. This is static
                # metadata, while the match-state badge above reflects runtime.
                conf = int(round(float(getattr(action, "similarity", 0.95) or 0.95) * 100))
                conf_rect = QRectF(max(text_x, text_right - (48 if compact else 58)), outer.center().y() + 7, 48 if compact else 58, 14)
                self._rounded_rect(painter, conf_rect, 4, COLORS["bg"], type_color, 1)
                painter.setPen(QColor(type_color))
                painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                painter.drawText(conf_rect, Qt.AlignmentFlag.AlignCenter, f"≥ {conf}%")

            if linked_target and kind != "group":
                link_rect = QRectF(text_x, outer.center().y() + 7, 46 if compact else 54, 14)
                self._rounded_rect(painter, link_rect, 4, COLORS["bg"], COLORS.get("accent", type_color), 1)
                painter.setPen(QColor(COLORS.get("accent", type_color)))
                painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                painter.drawText(link_rect, Qt.AlignmentFlag.AlignCenter, "TARGET")

            if traced and not playing and not linked_target:
                done_rect = QRectF(text_x, outer.center().y() + 7, 42 if compact else 50, 14)
                self._rounded_rect(painter, done_rect, 4, COLORS["bg"], COLORS.get("success", type_color), 1)
                painter.setPen(QColor(COLORS.get("success", type_color)))
                painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                painter.drawText(done_rect, Qt.AlignmentFlag.AlignCenter, "TRACE")

            if not enabled:
                disabled_rect = QRectF(text_x, outer.center().y() + 7, 54 if compact else 64, 14)
                self._rounded_rect(painter, disabled_rect, 4, COLORS["bg"], COLORS["text_dark"], 1)
                painter.setPen(QColor(COLORS["text_dark"]))
                painter.setFont(QFont("Segoe UI", 6 if compact else 7, QFont.Weight.DemiBold))
                painter.drawText(disabled_rect, Qt.AlignmentFlag.AlignCenter, "DISABLED")

            # Status chip. Its width is fixed and never collapses into a dot.
            if not enabled:
                status, status_col = "Disabled", COLORS["text_dark"]
            elif kind == "group":
                if group_drop_target:
                    status, status_col = "Drop in", COLORS.get("success", type_color)
                else:
                    status, status_col = ("Active", type_color) if active_group else ("Folder", type_color)
            elif kind == "loop":
                status, status_col = "Loop", type_color
            elif playing:
                status, status_col = ("Paused", COLORS["pause_cyan"]) if getattr(view, "paused", False) else ("Running", type_color)
            elif progress >= 0.999:
                status, status_col = "Completed", type_color
            else:
                status, status_col = "Pending", COLORS["text_dim"]

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

            insert_row = -1 if getattr(view, "drop_group_row", -1) >= 0 else getattr(view, "drop_insert_row", -1)
            line_y = None
            if insert_row == row:
                line_y = option.rect.top() + 1
            elif insert_row == row + 1 and row == view.model().rowCount() - 1:
                line_y = option.rect.bottom() - 1
            if line_y is not None:
                line_left = outer.left() + 8
                line_right = outer.right() - 8
                painter.setPen(QPen(QColor(COLORS["accent"]), 2))
                painter.drawLine(QPointF(line_left, line_y), QPointF(line_right, line_y))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(COLORS["accent"]))
                painter.drawEllipse(QRectF(line_left - 3, line_y - 3, 6, 6))
                painter.drawEllipse(QRectF(line_right - 3, line_y - 3, 6, 6))
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
        zoom = float(getattr(view, "zoom", 1.0) or 1.0)
        action = index.data(ActionListModel.ActionRole)
        base_height = 52 if getattr(action, "action_type", "") == "group" else (56 if getattr(option.widget, "width", lambda: 999)() < 700 else 64)
        height = max(42 if getattr(action, "action_type", "") == "group" else 48, int(base_height * zoom))
        return QSize(100, height)


class TimelineView(QListView):
    action_clicked = pyqtSignal(int)
    action_double_clicked = pyqtSignal(int)
    action_context_menu = pyqtSignal(int, object)
    action_dragged = pyqtSignal(int, int)
    action_dropped_into_group = pyqtSignal(int, int)
    group_toggle_requested = pyqtSignal(int)

    def __init__(self, parent=None, model=None):
        super().__init__(parent)

        # Start slightly compact by default while preserving Ctrl+wheel zoom.
        self.zoom = 0.90
        self.selected_indices = set()
        self.playing_index = -1
        self.next_index = -1
        self.active_group_id = ""
        self.paused = False
        self.image_states = {}
        self._search = ""
        self._drag_start_row = -1
        self._drag_allowed = False
        self.drag_source_row = -1
        self.drop_insert_row = -1
        self.drop_group_row = -1
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
                name = getattr(action, "group_name", "") or getattr(action, "label", "") or f"Group {len(headers) + 1}"
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
                    if kind == "image" and float(getattr(child, "wait_timeout", 0.0) or 0.0) > 0:
                        duration += float(getattr(child, "wait_timeout", 0.0) or 0.0)
                    else:
                        duration += float(getattr(child, "duration", 0.0) or 0.0)
                headers.append({
                    "row": row, "action": action, "gid": gid, "color": color,
                    "name": name, "badge": f"G{len(headers) + 1}",
                    "count": count, "duration": duration,
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
        self.link_source_row = int(source if source is not None else -1)
        self.link_target_rows = {int(t) for t in (targets or []) if t is not None and int(t) >= 0}
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

    def _row_outer_rect(self, row: int):
        """Return the painted row card rect used for hit-testing grip/kebab zones."""
        if row < 0 or self.model() is None or row >= self.model().rowCount():
            return QRectF()
        idx = self.model().index(row, 0)
        rect = self.visualRect(idx)
        if not rect.isValid():
            return QRectF()
        narrow = rect.width() < 700
        adjusted = rect.adjusted(8, 2, -8, -2) if narrow else rect.adjusted(14, 3, -20, -3)
        return QRectF(adjusted)

    def _drag_grip_rect(self, row: int):
        outer = self._row_outer_rect(row)
        if outer.isNull():
            return QRectF()
        compact = outer.width() < 760
        grip_x = outer.left() + (8 if compact else 12)
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
            self.sync_selection()
            if not self.selected_indices:
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
        if event.button() == Qt.MouseButton.LeftButton and idx.isValid():
            if self._row_kind(row) == "group" and self._is_kebab_hit(row, pos):
                self.group_toggle_requested.emit(row)
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
        self.drag_source_row = self._drag_start_row
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

    def dragMoveEvent(self, event):
        if event.source() is self:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self._last_drag_pos = pos
            self._update_auto_scroll(pos)
            group_row = self._drop_group_row(pos)
            if group_row >= 0:
                self.drop_group_row = group_row
                self.drop_insert_row = -1
            else:
                self.drop_group_row = -1
                self.drop_insert_row = self._drop_insert_row(pos)
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
            self.drop_insert_row = self._drop_insert_row(self._last_drag_pos)
            self.viewport().update()

    def _stop_auto_scroll(self):
        self._auto_scroll_direction = 0
        self._auto_scroll_timer.stop()

    def _stop_drag_feedback(self):
        self._stop_auto_scroll()
        self._drag_start_row = -1
        self._drag_allowed = False
        self.drag_source_row = -1
        self.drop_insert_row = -1
        self.drop_group_row = -1
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

    def _drop_group_row(self, pos) -> int:
        """Return a group header row when the cursor is in its central drop zone.

        Top/bottom edges still behave like normal reorder insertion targets, so
        users can move rows around a group without accidentally adding them to it.
        """
        if self.model() is None or self._drag_start_row < 0:
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
        if self.playing_index >= 0 or not self._drag_allowed:
            event.ignore()
            self._stop_drag_feedback()
            return
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        group_target = self._drop_group_row(pos)
        target = self._drop_target_row(pos) if group_target < 0 else -1
        self._stop_auto_scroll()
        event.acceptProposedAction()
        if source >= 0 and group_target >= 0:
            QTimer.singleShot(0, lambda s=source, g=group_target: self.action_dropped_into_group.emit(s, g))
        elif source >= 0 and target >= 0 and source != target:
            QTimer.singleShot(0, lambda s=source, t=target: self.action_dragged.emit(s, t))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            old = self.zoom
            delta = event.angleDelta().y()
            self.zoom = max(0.55, min(1.60, self.zoom * (1.08 if delta > 0 else 1 / 1.08)))
            if self.zoom != old:
                self.setUniformItemSizes(False)
                self.doItemsLayout()
                self.setUniformItemSizes(False)
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
            self.clearSelection()
            self.setCurrentIndex(idx)
            sel = self.selectionModel()
            if sel is not None:
                sel.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            self.selected_indices = {index}
        else:
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
            self.selected_indices.clear()
        self.viewport().update()

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
        self._playing_duration = max(0.0, float(duration or 0.0))
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
