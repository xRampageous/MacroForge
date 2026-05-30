"""Click action dialog — modern PyQt6 rebuild."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QCheckBox
)
from models import Action
from ui.theme import COLORS


class ClickDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Click Action")
        self.setMinimumWidth(360)
        C = COLORS
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C['bg']}; }}
            QLabel {{ color: {C['text_dim']}; font-size: 12px; }}
            QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; font-size: 12px; }}
            QLineEdit:focus {{ border-color: {C['accent']}; }}
            QComboBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 10px; }}
        """)

        lo = QVBoxLayout(self)
        lo.setSpacing(10)
        lo.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel("CLICK")
        hdr.setStyleSheet(f"color: {C['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lo.addWidget(hdr)

        # Coordinates
        coord = QHBoxLayout()
        coord.addWidget(QLabel("X"))
        self.x = QLineEdit(str(getattr(existing, 'click_x', 0)) if existing else "0")
        self.x.setFixedWidth(60)
        coord.addWidget(self.x)
        coord.addWidget(QLabel("Y"))
        self.y = QLineEdit(str(getattr(existing, 'click_y', 0)) if existing else "0")
        self.y.setFixedWidth(60)
        coord.addWidget(self.y)
        coord.addStretch()
        lo.addLayout(coord)

        # Button
        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("Button"))
        self.btn = QComboBox()
        self.btn.addItems(["left", "right", "middle", "double"])
        self.btn.setCurrentText(getattr(existing, 'click_button', 'left') if existing else 'left')
        btn_row.addWidget(self.btn)
        btn_row.addStretch()
        lo.addLayout(btn_row)

        # Random radius
        rand_row = QHBoxLayout()
        rand_row.addWidget(QLabel("Random ± (px)"))
        self.rand = QLineEdit(str(getattr(existing, 'click_rand_radius', 0)) if existing else "0")
        self.rand.setFixedWidth(50)
        rand_row.addWidget(self.rand)
        rand_row.addStretch()
        lo.addLayout(rand_row)

        # Repeat
        rep_row = QHBoxLayout()
        rep_row.addWidget(QLabel("Repeat ×"))
        self.rep = QLineEdit(str(getattr(existing, 'repeat_count', 1)) if existing else "1")
        self.rep.setFixedWidth(50)
        rep_row.addWidget(self.rep)
        rep_row.addStretch()
        lo.addLayout(rep_row)

        # Label
        lbl_row = QHBoxLayout()
        lbl_row.addWidget(QLabel("Label"))
        self.lbl = QLineEdit(getattr(existing, 'label', '') if existing else '')
        lbl_row.addWidget(self.lbl)
        lo.addLayout(lbl_row)

        lo.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(f"background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 8px 16px;")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Add Click")
        ok.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['accent']},stop:1 {C['accent_secondary']}); color: {C['text_inverse']}; border: none; border-radius: 10px; padding: 8px 16px; font-weight: 700;")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        lo.addLayout(btn_row)

    def get_action(self):
        try:
            x = int(self.x.text())
            y = int(self.y.text())
            rand = int(self.rand.text() or 0)
        except ValueError:
            return None
        return Action(
            key="[CLICK]",
            duration=0.05,
            action_type="click",
            click_x=x,
            click_y=y,
            click_button=self.btn.currentText(),
            click_rand_radius=rand,
            repeat_count=max(1, int(self.rep.text() or 1)),
            label=self.lbl.text().strip()
        )
