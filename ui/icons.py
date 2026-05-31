"""MacroForge icon renderer — self-contained, no external assets.
Draws common UI icons as QPixmap using QPainter paths.
"""
from PyQt6.QtCore import Qt, QSize, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont, QIcon


def _make_pixmap(size, draw_fn):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_fn(p, size)
    p.end()
    return pm


def icon(name: str, size: int = 16, color: str = "#e0e2f0") -> QPixmap:
    c = QColor(color)
    pen = QPen(c, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    brush = QBrush(c)

    def _draw_play(p, s):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        p.drawPolygon([
            QPointF(s * 0.28, s * 0.2), QPointF(s * 0.28, s * 0.8), QPointF(s * 0.78, s * 0.5)
        ])

    def _draw_pause(p, s):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        p.drawRect(int(s * 0.25), int(s * 0.22), int(s * 0.18), int(s * 0.56))
        p.drawRect(int(s * 0.57), int(s * 0.22), int(s * 0.18), int(s * 0.56))

    def _draw_stop(p, s):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        p.drawRect(int(s * 0.26), int(s * 0.26), int(s * 0.48), int(s * 0.48))

    def _draw_record(p, s):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        p.drawEllipse(int(s * 0.25), int(s * 0.25), int(s * 0.5), int(s * 0.5))

    def _draw_key(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.18, s * 0.28, s * 0.64, s * 0.44), 3, 3)

    def _draw_click(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * 0.18, s * 0.18, s * 0.64, s * 0.64))

    def _draw_image(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.15, s * 0.22, s * 0.7, s * 0.56), 3, 3)
        p.drawLine(int(s * 0.15), int(s * 0.58), int(s * 0.42), int(s * 0.38))
        p.drawLine(int(s * 0.42), int(s * 0.38), int(s * 0.65), int(s * 0.52))
        p.drawLine(int(s * 0.65), int(s * 0.52), int(s * 0.85), int(s * 0.42))

    def _draw_delay(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(int(s * 0.15), int(s * 0.15), int(s * 0.7), int(s * 0.7), 90 * 16, -270 * 16)
        p.drawLine(int(s * 0.62), int(s * 0.22), int(s * 0.72), int(s * 0.32),)
        p.drawLine(int(s * 0.72), int(s * 0.32), int(s * 0.62), int(s * 0.32))

    def _draw_plus(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.5), int(s * 0.2), int(s * 0.5), int(s * 0.8))
        p.drawLine(int(s * 0.2), int(s * 0.5), int(s * 0.8), int(s * 0.5))

    def _draw_trash(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(int(s * 0.3), int(s * 0.22), int(s * 0.7), int(s * 0.22))
        p.drawLine(int(s * 0.42), int(s * 0.22), int(s * 0.42), int(s * 0.16))
        p.drawLine(int(s * 0.58), int(s * 0.22), int(s * 0.58), int(s * 0.16))
        p.drawLine(int(s * 0.36), int(s * 0.16), int(s * 0.64), int(s * 0.16))
        p.drawRoundedRect(QRectF(s * 0.28, s * 0.28, s * 0.44, s * 0.5), 2, 2)
        p.drawLine(int(s * 0.42), int(s * 0.42), int(s * 0.42), int(s * 0.62))
        p.drawLine(int(s * 0.58), int(s * 0.42), int(s * 0.58), int(s * 0.62))

    def _draw_duplicate(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.18, s * 0.22, s * 0.46, s * 0.56), 2, 2)
        p.drawRoundedRect(QRectF(s * 0.38, s * 0.18, s * 0.46, s * 0.56), 2, 2)

    def _draw_edit(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.72), int(s * 0.18), int(s * 0.82), int(s * 0.28))
        p.drawLine(int(s * 0.28), int(s * 0.72), int(s * 0.82), int(s * 0.18))
        p.drawLine(int(s * 0.18), int(s * 0.82), int(s * 0.28), int(s * 0.72))

    def _draw_check(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.22), int(s * 0.52), int(s * 0.42), int(s * 0.72))
        p.drawLine(int(s * 0.42), int(s * 0.72), int(s * 0.82), int(s * 0.28))

    def _draw_cross(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.22), int(s * 0.22), int(s * 0.78), int(s * 0.78))
        p.drawLine(int(s * 0.78), int(s * 0.22), int(s * 0.22), int(s * 0.78))

    def _draw_bolt(p, s):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        p.drawPolygon([
            QPointF(s * 0.55, s * 0.12), QPointF(s * 0.35, s * 0.48), QPointF(s * 0.52, s * 0.52),
            QPointF(s * 0.42, s * 0.88), QPointF(s * 0.65, s * 0.44), QPointF(s * 0.48, s * 0.4)
        ])

    def _draw_loop(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(int(s * 0.15), int(s * 0.25), int(s * 0.5), int(s * 0.5), 0, 270 * 16)
        p.drawLine(int(s * 0.65), int(s * 0.35), int(s * 0.75), int(s * 0.28))
        p.drawLine(int(s * 0.75), int(s * 0.28), int(s * 0.72), int(s * 0.42))

    def _draw_clock(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * 0.15, s * 0.15, s * 0.7, s * 0.7))
        p.drawLine(int(s * 0.5), int(s * 0.28), int(s * 0.5), int(s * 0.5))
        p.drawLine(int(s * 0.5), int(s * 0.5), int(s * 0.65), int(s * 0.58))

    def _draw_menu(p, s):
        p.setPen(pen)
        for y in (0.28, 0.5, 0.72):
            p.drawLine(int(s * 0.2), int(s * y), int(s * 0.8), int(s * y))

    def _draw_update(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(int(s * 0.15), int(s * 0.22), int(s * 0.7), int(s * 0.56), 0, -200 * 16)
        p.drawLine(int(s * 0.55), int(s * 0.15), int(s * 0.72), int(s * 0.28))
        p.drawLine(int(s * 0.72), int(s * 0.28), int(s * 0.55), int(s * 0.38))

    def _draw_move(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.5), int(s * 0.15), int(s * 0.5), int(s * 0.85))
        p.drawLine(int(s * 0.2), int(s * 0.35), int(s * 0.5), int(s * 0.15))
        p.drawLine(int(s * 0.8), int(s * 0.35), int(s * 0.5), int(s * 0.15))
        p.drawLine(int(s * 0.2), int(s * 0.65), int(s * 0.5), int(s * 0.85))
        p.drawLine(int(s * 0.8), int(s * 0.65), int(s * 0.5), int(s * 0.85))

    def _draw_settings(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * 0.35, s * 0.35, s * 0.3, s * 0.3))
        p.drawArc(int(s * 0.15), int(s * 0.15), int(s * 0.7), int(s * 0.7), 0, 360 * 16)
        for ang in (0, 45, 90, 135, 180, 225, 270, 315):
            import math
            rad = math.radians(ang)
            x1 = s * (0.5 + 0.22 * math.cos(rad))
            y1 = s * (0.5 + 0.22 * math.sin(rad))
            x2 = s * (0.5 + 0.36 * math.cos(rad))
            y2 = s * (0.5 + 0.36 * math.sin(rad))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _draw_browse(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.18), int(s * 0.72), int(s * 0.5), int(s * 0.28))
        p.drawLine(int(s * 0.5), int(s * 0.28), int(s * 0.82), int(s * 0.72))
        p.drawLine(int(s * 0.3), int(s * 0.72), int(s * 0.7), int(s * 0.72))

    def _draw_condition(p, s):
        # Diamond (decision node)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon([
            QPointF(s * 0.5, s * 0.15), QPointF(s * 0.85, s * 0.5),
            QPointF(s * 0.5, s * 0.85), QPointF(s * 0.15, s * 0.5),
        ])

    def _draw_save(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6), 2, 2)
        p.drawRect(int(s * 0.36), int(s * 0.2), int(s * 0.28), int(s * 0.22))
        p.drawRect(int(s * 0.34), int(s * 0.52), int(s * 0.32), int(s * 0.28))

    def _draw_folder(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(int(s * 0.15), int(s * 0.3), int(s * 0.4), int(s * 0.3))
        p.drawLine(int(s * 0.4), int(s * 0.3), int(s * 0.48), int(s * 0.38))
        p.drawRoundedRect(QRectF(s * 0.15, s * 0.3, s * 0.7, s * 0.45), 3, 3)

    def _draw_undo(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(int(s * 0.22), int(s * 0.28), int(s * 0.56), int(s * 0.5), 30 * 16, 200 * 16)
        p.drawLine(int(s * 0.22), int(s * 0.3), int(s * 0.22), int(s * 0.5))
        p.drawLine(int(s * 0.22), int(s * 0.3), int(s * 0.42), int(s * 0.3))

    def _draw_redo(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(int(s * 0.22), int(s * 0.28), int(s * 0.56), int(s * 0.5), -50 * 16, -200 * 16)
        p.drawLine(int(s * 0.78), int(s * 0.3), int(s * 0.78), int(s * 0.5))
        p.drawLine(int(s * 0.78), int(s * 0.3), int(s * 0.58), int(s * 0.3))

    def _draw_search(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * 0.2, s * 0.2, s * 0.42, s * 0.42))
        p.drawLine(int(s * 0.58), int(s * 0.58), int(s * 0.82), int(s * 0.82))

    def _draw_eye(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(int(s * 0.12), int(s * 0.18), int(s * 0.76), int(s * 0.64), 20 * 16, 140 * 16)
        p.drawArc(int(s * 0.12), int(s * 0.18), int(s * 0.76), int(s * 0.64), 200 * 16, 140 * 16)
        p.setBrush(brush)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(s * 0.42, s * 0.42, s * 0.16, s * 0.16))

    def _draw_target(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(s * 0.2, s * 0.2, s * 0.6, s * 0.6))
        p.drawLine(int(s * 0.5), int(s * 0.08), int(s * 0.5), int(s * 0.28))
        p.drawLine(int(s * 0.5), int(s * 0.72), int(s * 0.5), int(s * 0.92))
        p.drawLine(int(s * 0.08), int(s * 0.5), int(s * 0.28), int(s * 0.5))
        p.drawLine(int(s * 0.72), int(s * 0.5), int(s * 0.92), int(s * 0.5))
        p.setBrush(brush)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(s * 0.43, s * 0.43, s * 0.14, s * 0.14))

    def _draw_camera(p, s):
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.12, s * 0.3, s * 0.76, s * 0.5), 3, 3)
        p.drawRect(int(s * 0.36), int(s * 0.22), int(s * 0.28), int(s * 0.1))
        p.drawEllipse(QRectF(s * 0.38, s * 0.42, s * 0.24, s * 0.24))

    def _draw_chevron(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.35), int(s * 0.25), int(s * 0.6), int(s * 0.5))
        p.drawLine(int(s * 0.6), int(s * 0.5), int(s * 0.35), int(s * 0.75))

    def _draw_minimize(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.25), int(s * 0.7), int(s * 0.75), int(s * 0.7))

    def _draw_close(p, s):
        p.setPen(pen)
        p.drawLine(int(s * 0.28), int(s * 0.28), int(s * 0.72), int(s * 0.72))
        p.drawLine(int(s * 0.72), int(s * 0.28), int(s * 0.28), int(s * 0.72))

    def _draw_grip(p, s):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(brush)
        for gx in (0.4, 0.6):
            for gy in (0.3, 0.5, 0.7):
                p.drawEllipse(QRectF(s * gx - s * 0.05, s * gy - s * 0.05, s * 0.1, s * 0.1))

    dispatch = {
        "play": _draw_play, "pause": _draw_pause, "stop": _draw_stop,
        "record": _draw_record, "key": _draw_key, "click": _draw_click,
        "image": _draw_image, "delay": _draw_delay, "plus": _draw_plus,
        "trash": _draw_trash, "duplicate": _draw_duplicate, "edit": _draw_edit,
        "check": _draw_check, "cross": _draw_cross, "bolt": _draw_bolt,
        "loop": _draw_loop, "clock": _draw_clock, "menu": _draw_menu,
        "update": _draw_update, "move": _draw_move, "settings": _draw_settings,
        "browse": _draw_browse, "condition": _draw_condition, "save": _draw_save,
        "folder": _draw_folder, "undo": _draw_undo, "redo": _draw_redo,
        "search": _draw_search, "eye": _draw_eye, "target": _draw_target,
        "camera": _draw_camera, "chevron": _draw_chevron, "minimize": _draw_minimize,
        "close": _draw_close, "grip": _draw_grip,
    }
    fn = dispatch.get(name)
    if fn:
        return QIcon(_make_pixmap(size, fn))
    return QIcon()
