"""MacroForge icon renderer — self-contained, no external assets.
Draws common UI icons as QPixmap using QPainter paths.
"""
from PyQt6.QtCore import Qt, QSize, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont, QIcon


def _make_pixmap(size, draw_fn):
    """Render icons safely at high resolution, then downsample.

    This keeps small icons sharp without using devicePixelRatio tricks that can
    make QIcon/QPixmap render clipped or offset on some Windows/Qt setups.
    """
    scale = 3
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.scale(scale, scale)
    draw_fn(p, size)
    p.end()

    return pm.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def timeline_action_icon(kind: str, size: int = 18, color: str = "#F3F6FA") -> QIcon:
    """Render the exact compact action-type glyphs used by the timeline rows.

    The Add Action buttons use this helper so their icons stay visually synced
    with ``TimelineDelegate._draw_type_icon`` instead of drifting from the
    timeline glyph language.
    """
    normalized = (kind or "key").lower()
    if normalized == "delay":
        normalized = "pause"
    elif normalized == "folder":
        normalized = "group"

    c = QColor(color)
    pen_w = 1.8 if size <= 20 else max(1.8, size * 0.09)
    pen = QPen(c, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    def _draw_timeline_action(p, s):
        x, y, w, h = 0.0, 0.0, float(s), float(s)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        if normalized == "pause":
            p.drawEllipse(QRectF(x + w * 0.22, y + h * 0.22, w * 0.56, h * 0.56))
            p.drawLine(int(x + w * 0.50), int(y + h * 0.34), int(x + w * 0.50), int(y + h * 0.52))
            p.drawLine(int(x + w * 0.50), int(y + h * 0.52), int(x + w * 0.64), int(y + h * 0.60))
        elif normalized == "click":
            p.drawEllipse(QRectF(x + w * 0.28, y + h * 0.20, w * 0.44, h * 0.62))
            p.drawLine(int(x + w * 0.50), int(y + h * 0.20), int(x + w * 0.50), int(y + h * 0.42))
            p.drawLine(int(x + w * 0.28), int(y + h * 0.42), int(x + w * 0.72), int(y + h * 0.42))
        elif normalized == "image":
            p.drawRoundedRect(QRectF(x + w * 0.20, y + h * 0.25, w * 0.60, h * 0.50), 3, 3)
            p.drawLine(int(x + w * 0.23), int(y + h * 0.62), int(x + w * 0.42), int(y + h * 0.45))
            p.drawLine(int(x + w * 0.42), int(y + h * 0.45), int(x + w * 0.58), int(y + h * 0.56))
            p.drawLine(int(x + w * 0.58), int(y + h * 0.56), int(x + w * 0.76), int(y + h * 0.40))
        elif normalized == "condition":
            p.drawPolygon([
                QPointF(x + w * 0.50, y + h * 0.18), QPointF(x + w * 0.82, y + h * 0.50),
                QPointF(x + w * 0.50, y + h * 0.82), QPointF(x + w * 0.18, y + h * 0.50),
            ])
        elif normalized == "group":
            p.drawRoundedRect(QRectF(x + w * 0.18, y + h * 0.34, w * 0.64, h * 0.40), 3, 3)
            p.drawLine(int(x + w * 0.25), int(y + h * 0.34), int(x + w * 0.36), int(y + h * 0.25))
            p.drawLine(int(x + w * 0.36), int(y + h * 0.25), int(x + w * 0.54), int(y + h * 0.25))
        elif normalized == "loop":
            p.drawArc(int(x + w * 0.22), int(y + h * 0.24), int(w * 0.56), int(h * 0.52), 35 * 16, 285 * 16)
            p.drawLine(int(x + w * 0.70), int(y + h * 0.30), int(x + w * 0.82), int(y + h * 0.30))
            p.drawLine(int(x + w * 0.82), int(y + h * 0.30), int(x + w * 0.77), int(y + h * 0.42))
        else:
            p.drawRoundedRect(QRectF(x + w * 0.18, y + h * 0.28, w * 0.64, h * 0.44), 3, 3)
            for px in (0.30, 0.46, 0.62):
                p.drawPoint(QPointF(x + w * px, y + h * 0.42))
            p.drawLine(int(x + w * 0.34), int(y + h * 0.58), int(x + w * 0.66), int(y + h * 0.58))

    return QIcon(_make_pixmap(size, _draw_timeline_action))


def icon(name: str, size: int = 16, color: str = "#e0e2f0") -> QIcon:
    c = QColor(color)
    pen_w = 1.8 if size <= 18 else max(1.8, size * 0.10)
    pen = QPen(c, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
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


    def _draw_magic(p, s):
        # Wand with tiny sparkle accents for the top toolbar quick-action button.
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(int(s * 0.24), int(s * 0.76), int(s * 0.70), int(s * 0.30))
        p.drawLine(int(s * 0.63), int(s * 0.23), int(s * 0.77), int(s * 0.37))
        p.drawLine(int(s * 0.57), int(s * 0.29), int(s * 0.71), int(s * 0.43))
        # small sparkle top-left
        p.drawLine(int(s * 0.22), int(s * 0.20), int(s * 0.22), int(s * 0.34))
        p.drawLine(int(s * 0.15), int(s * 0.27), int(s * 0.29), int(s * 0.27))
        # small sparkle right
        p.drawLine(int(s * 0.82), int(s * 0.56), int(s * 0.82), int(s * 0.68))
        p.drawLine(int(s * 0.76), int(s * 0.62), int(s * 0.88), int(s * 0.62))

    def _draw_key(p, s):
        # Keyboard silhouette with a few key rows
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(s * 0.12, s * 0.22, s * 0.76, s * 0.56), 2, 2)
        # top row keys
        for x in (0.22, 0.42, 0.62):
            p.drawRect(int(s * x), int(s * 0.30), int(s * 0.14), int(s * 0.14))
        # bottom row (spacebar-ish)
        p.drawRect(int(s * 0.30), int(s * 0.50), int(s * 0.40), int(s * 0.14))

    def _draw_click(p, s):
        # Mouse silhouette
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # body
        p.drawEllipse(QRectF(s * 0.22, s * 0.18, s * 0.56, s * 0.70))
        # scroll wheel / button split
        p.drawLine(int(s * 0.50), int(s * 0.18), int(s * 0.50), int(s * 0.42))
        # horizontal split for left/right buttons
        p.drawLine(int(s * 0.22), int(s * 0.42), int(s * 0.78), int(s * 0.42))

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
        "magic": _draw_magic,
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
