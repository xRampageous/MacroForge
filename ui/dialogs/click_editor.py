"""Click editor dialog for MacroForge PyQt6."""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton, QHBoxLayout, QComboBox, QLabel
from PyQt6.QtCore import Qt

from ui.theme import COLORS
from models import Action


class ClickEditorDialog(QDialog):
    """Dialog to edit click action properties."""

    def __init__(self, parent, action: Action):
        super().__init__(parent)
        self._action = action
        self.setWindowTitle("Edit Click Action")
        self.resize(380, 350)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._spin_x = QSpinBox()
        self._spin_x.setRange(-9999, 9999)
        self._spin_x.setValue(getattr(self._action, "click_x", 0))
        form.addRow("Click X:", self._spin_x)

        self._spin_y = QSpinBox()
        self._spin_y.setRange(-9999, 9999)
        self._spin_y.setValue(getattr(self._action, "click_y", 0))
        form.addRow("Click Y:", self._spin_y)

        self._combo_btn = QComboBox()
        self._combo_btn.addItems(["left", "right", "middle", "double"])
        self._combo_btn.setCurrentText(getattr(self._action, "click_button", "left"))
        form.addRow("Button:", self._combo_btn)

        self._combo_mode = QComboBox()
        self._combo_mode.addItems(["absolute", "foreground", "offset", "current"])
        self._combo_mode.setCurrentText(getattr(self._action, "click_coord_mode", "absolute"))
        form.addRow("Coord mode:", self._combo_mode)

        self._spin_rand = QSpinBox()
        self._spin_rand.setRange(0, 100)
        self._spin_rand.setValue(getattr(self._action, "click_rand_radius", 0))
        form.addRow("Random radius:", self._spin_rand)

        self._chk_hold = QCheckBox()
        self._chk_hold.setChecked(self._action.hold_mode)
        form.addRow("Hold mode:", self._chk_hold)

        self._spin_dur = QDoubleSpinBox()
        self._spin_dur.setRange(0.01, 10)
        self._spin_dur.setValue(self._action.duration)
        form.addRow("Duration (s):", self._spin_dur)

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
        self._action.click_x = self._spin_x.value()
        self._action.click_y = self._spin_y.value()
        self._action.click_button = self._combo_btn.currentText()
        self._action.click_coord_mode = self._combo_mode.currentText()
        self._action.click_rand_radius = self._spin_rand.value()
        self._action.hold_mode = self._chk_hold.isChecked()
        self._action.duration = self._spin_dur.value()
        self.accept()
