"""Pause / Delay action dialog — modern PyQt6 rebuild."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
)
from models import Action
from ui.theme import COLORS
from ui.dialogs._common import dialog_stylesheet, make_header, make_buttons


class PauseDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Delay Action")
        self.setMinimumWidth(320)
        C = COLORS
        self._accent = C['pause']
        self.setStyleSheet(dialog_stylesheet(self._accent))

        lo = QVBoxLayout(self)
        lo.setSpacing(9)
        lo.setContentsMargins(16, 16, 16, 14)

        lo.addWidget(make_header("Delay", self._accent, "delay", "Wait for a fixed duration"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Duration (s)"))
        self.dur = QLineEdit(str(existing.duration) if existing else "1.0")
        self.dur.setFixedWidth(80)
        row.addWidget(self.dur)
        row.addStretch()
        lo.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Label"))
        self.lbl = QLineEdit(getattr(existing, 'label', '') if existing else '')
        row2.addWidget(self.lbl)
        lo.addLayout(row2)

        lo.addStretch()
        lo.addLayout(make_buttons(self, "Add Delay", self._accent, self.accept, "delay"))

    def get_action(self):
        try:
            dur = float(self.dur.text())
            if dur <= 0:
                raise ValueError
        except ValueError:
            return None
        return Action(
            key="[DELAY]",
            duration=dur,
            action_type="pause",
            label=self.lbl.text().strip()
        )
