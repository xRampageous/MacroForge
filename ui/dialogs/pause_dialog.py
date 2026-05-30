"""Pause / Delay action dialog — modern PyQt6 rebuild."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
)
from models import Action
from ui.theme import COLORS


class PauseDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Delay Action")
        self.setMinimumWidth(320)
        C = COLORS
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C['bg']}; }}
            QLabel {{ color: {C['text_dim']}; font-size: 12px; }}
            QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; font-size: 12px; }}
            QLineEdit:focus {{ border-color: {C['accent']}; }}
        """)

        lo = QVBoxLayout(self)
        lo.setSpacing(10)
        lo.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel("DELAY")
        hdr.setStyleSheet(f"color: {C['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lo.addWidget(hdr)

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
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 8px 16px;")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Add Delay")
        ok.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['accent']},stop:1 {C['accent_secondary']}); color: {C['text_inverse']}; border: none; border-radius: 10px; padding: 8px 16px; font-weight: 700;")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        lo.addLayout(btn_row)

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
