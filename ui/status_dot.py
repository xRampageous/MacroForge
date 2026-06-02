"""Small status widgets shared by the main window."""
import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter
from PyQt6.QtWidgets import QWidget

from ui.theme import COLORS


class StatusDot(QWidget):
    """Animated glowing status indicator."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(COLORS["text_dark"])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._pulse_phase = 0.0
        self._glow = False

    def set_color(self, color_hex, glow=False):
        self._color = QColor(color_hex)
        self._glow = glow
        if glow and not self._timer.isActive():
            self._timer.start(50)
        elif not glow and self._timer.isActive():
            self._timer.stop()
            self._pulse_phase = 0.0
        self.update()

    def _pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.15) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = int(self.width() / 2), int(self.height() / 2)
        radius = 4
        if self._glow:
            glow_radius = int(5 + math.sin(self._pulse_phase) * 2)
            painter.setBrush(QBrush(QColor(f"{self._color.name()}30")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                cx - glow_radius,
                cy - glow_radius,
                glow_radius * 2,
                glow_radius * 2,
            )
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
