"""Key action dialog — modern PyQt6 rebuild."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QPushButton, QComboBox, QFrame
)
from PyQt6.QtCore import Qt
from models import Action
from ui.theme import COLORS

KEY_VALUES = ["a","b","c","d","e","f","g","h","i","j","k","l","m",
              "n","o","p","q","r","s","t","u","v","w","x","y","z",
              "0","1","2","3","4","5","6","7","8","9",
              "space","return","tab","esc","backspace",
              "up","down","left","right","f1","f2","f3","f4","f5","f6",
              "f7","f8","f9","f10","f11","f12"]

class KeyDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Key Action")
        self.setMinimumWidth(380)
        C = COLORS
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C['bg']}; }}
            QLabel {{ color: {C['text_dim']}; font-size: 12px; }}
            QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; font-size: 12px; }}
            QLineEdit:focus {{ border-color: {C['accent']}; }}
            QComboBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; }}
            QCheckBox {{ color: {C['text_dim']}; font-size: 12px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['border']}; border-radius: 5px; }}
            QCheckBox::indicator:checked {{ background-color: {C['accent']}; border-color: {C['accent']}; }}
        """)

        lo = QVBoxLayout(self)
        lo.setSpacing(10)
        lo.setContentsMargins(16, 16, 16, 16)

        # Section header
        hdr = QLabel("KEY PRESS")
        hdr.setStyleSheet(f"color: {C['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lo.addWidget(hdr)

        # Key
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Key"))
        self.key_combo = QComboBox()
        self.key_combo.addItems(KEY_VALUES)
        self.key_combo.setEditable(True)
        self.key_combo.setCurrentText(existing.key if existing else "w")
        key_row.addWidget(self.key_combo, stretch=1)
        lo.addLayout(key_row)

        # Section
        hdr2 = QLabel("TIMING & BEHAVIOUR")
        hdr2.setStyleSheet(f"color: {C['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lo.addWidget(hdr2)

        # Fields
        self._flds = {}
        self.dur = self._field("Duration (s)", str(existing.duration) if existing else "0.5")
        self.rand = self._field("Random ± (s)", str(existing.random_delay) if existing else "0.0")
        self.rep = self._field("Repeat ×", str(getattr(existing, 'repeat_count', 1)) if existing else "1")
        self.lbl = self._field("Label", getattr(existing, 'label', '') if existing else '')
        for row in (self.dur, self.rand, self.rep, self.lbl):
            lo.addLayout(row)

        # Flags
        flags = QHBoxLayout()
        self.hold = QCheckBox("Hold key down")
        self.hold.setChecked(existing.hold_mode if existing else True)
        self.lane = QCheckBox("Lane 1 only")
        self.lane.setChecked((existing.lane == 1) if existing else False)
        self.rndK = QCheckBox("Random key")
        self.rndK.setChecked(existing.random_key if existing else False)
        for cb in (self.hold, self.lane, self.rndK):
            flags.addWidget(cb)
        flags.addStretch()
        lo.addLayout(flags)

        # Buttons
        lo.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 8px 16px;")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Add Key")
        ok.setObjectName("accent")
        ok.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['accent']},stop:1 {C['accent_secondary']}); color: {C['text_inverse']}; border: none; border-radius: 10px; padding: 8px 16px; font-weight: 700;")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        lo.addLayout(btn_row)

    def _field(self, label, value):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        le = QLineEdit(value)
        le.setFixedWidth(70)
        row.addWidget(le)
        row.addStretch()
        self._flds[label] = le
        return row

    def get_action(self):
        try:
            dur = float(self._flds["Duration (s)"].text())
            if dur <= 0:
                raise ValueError
        except (ValueError, AttributeError):
            return None
        k = self.key_combo.currentText().strip() or "w"
        lane = 1 if self.lane.isChecked() else 0
        return Action(
            key=k,
            duration=dur,
            hold_mode=self.hold.isChecked(),
            lane=lane,
            random_delay=float(self._flds["Random ± (s)"].text() or 0),
            random_key=self.rndK.isChecked(),
            label=self._flds["Label"].text().strip(),
            repeat_count=max(1, int(self._flds["Repeat ×"].text() or 1))
        )
