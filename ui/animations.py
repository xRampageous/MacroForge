"""PyQt6 animation utilities for MacroForge."""
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect


class Animator:
    """Helper for common PyQt6 animations."""

    @staticmethod
    def fade_in(widget: QWidget, duration: int = 300):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start()
        return anim

    @staticmethod
    def fade_out(widget: QWidget, duration: int = 200, on_finish=None):
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        if on_finish:
            anim.finished.connect(on_finish)
        anim.start()
        return anim

    @staticmethod
    def slide_up(widget: QWidget, distance: int = 20, duration: int = 300):
        anim = QPropertyAnimation(widget, b"pos")
        anim.setDuration(duration)
        start = widget.pos()
        anim.setStartValue(QPoint(start.x(), start.y() + distance))
        anim.setEndValue(start)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        return anim

    @staticmethod
    def pulse(widget: QWidget, duration: int = 800):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setKeyValueAt(0.5, 0.4)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)
        anim.start()
        return anim

    @staticmethod
    def bounce_height(widget: QWidget, delta: int = 8, duration: int = 400):
        anim = QPropertyAnimation(widget, b"maximumHeight")
        anim.setDuration(duration)
        h = widget.maximumHeight()
        anim.setStartValue(h)
        anim.setKeyValueAt(0.3, h + delta)
        anim.setEndValue(h)
        anim.setEasingCurve(QEasingCurve.Type.OutBounce)
        anim.start()
        return anim
