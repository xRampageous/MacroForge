"""Pause/delay editor dialog for MacroForge PyQt6."""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ui.theme import COLORS
from models import Action


class PauseEditorDialog(QDialog):
    """Dialog to edit pause action properties."""

    def __init__(self, parent, action: Action):
        super().__init__(parent)
        self._action = action
        self.setWindowTitle("Edit Delay Action")
        self.resize(340, 220)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._spin_dur = QDoubleSpinBox()
        self._spin_dur.setRange(0.01, 3600)
        self._spin_dur.setSingleStep(0.1)
        self._spin_dur.setValue(self._action.duration)
        form.addRow("Duration (s):", self._spin_dur)

        self._spin_lane = QSpinBox()
        self._spin_lane.setRange(0, 7)
        self._spin_lane.setValue(self._action.lane)
        form.addRow("Lane:", self._spin_lane)

        self._chk_rand = QCheckBox()
        self._chk_rand.setChecked(getattr(self._action, "random_delay", 0.0) > 0)
        form.addRow("Random delay:", self._chk_rand)

        self._spin_repeat = QSpinBox()
        self._spin_repeat.setRange(1, 100)
        self._spin_repeat.setValue(getattr(self._action, "repeat_count", 1))
        form.addRow("Repeat count:", self._spin_repeat)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("accent")
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def _on_ok(self):
        self._action.duration = self._spin_dur.value()
        self._action.lane = self._spin_lane.value()
        if self._chk_rand.isChecked():
            self._action.random_delay = 0.5
        else:
            self._action.random_delay = 0.0
        self._action.repeat_count = self._spin_repeat.value()
        self.accept()
