"""Key editor dialog for MacroForge PyQt6."""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton, QHBoxLayout, QComboBox, QLabel
from PyQt6.QtCore import Qt

from ui.theme import COLORS
from models import Action

KEY_VALUES = [
    "w","a","s","d","1","2","3","4","5","6","7","8","9","0",
    "q","e","r","t","y","u","i","o","p","f","g","h","j","k","l",
    "z","x","c","v","b","n","m",
    "enter","space","shift","ctrl","alt","tab","esc","backspace","delete",
    "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12",
    "up","down","left","right","home","end","pageup","pagedown",
    "insert","printscreen","pause"
]


class KeyEditorDialog(QDialog):
    """Dialog to edit key action properties."""

    def __init__(self, parent, action: Action):
        super().__init__(parent)
        self._action = action
        self.setWindowTitle("Edit Key Action")
        self.resize(380, 300)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._combo_key = QComboBox()
        self._combo_key.setEditable(True)
        self._combo_key.addItems(KEY_VALUES)
        self._combo_key.setCurrentText(self._action.key)
        form.addRow("Key:", self._combo_key)

        self._spin_dur = QDoubleSpinBox()
        self._spin_dur.setRange(0.01, 10)
        self._spin_dur.setSingleStep(0.01)
        self._spin_dur.setValue(self._action.duration)
        form.addRow("Duration (s):", self._spin_dur)

        self._chk_hold = QCheckBox()
        self._chk_hold.setChecked(self._action.hold_mode)
        form.addRow("Hold mode:", self._chk_hold)

        self._spin_lane = QSpinBox()
        self._spin_lane.setRange(0, 7)
        self._spin_lane.setValue(self._action.lane)
        form.addRow("Lane:", self._spin_lane)

        self._chk_rand = QCheckBox()
        self._chk_rand.setChecked(self._action.random_key)
        form.addRow("Random key:", self._chk_rand)

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
        self._action.key = self._combo_key.currentText()
        self._action.duration = self._spin_dur.value()
        self._action.hold_mode = self._chk_hold.isChecked()
        self._action.lane = self._spin_lane.value()
        self._action.random_key = self._chk_rand.isChecked()
        self.accept()
