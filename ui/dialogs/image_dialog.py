"""Image search action dialog — modern PyQt6 rebuild."""
import base64
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtGui import QPixmap
from models import Action
from ui.theme import COLORS


class ImageDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Image Search Action")
        self.setMinimumWidth(420)
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

        hdr = QLabel("IMAGE SEARCH")
        hdr.setStyleSheet(f"color: {C['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        lo.addWidget(hdr)

        # Image file
        img_row = QHBoxLayout()
        self.img_path = QLineEdit()
        self.img_path.setPlaceholderText("Select image file...")
        self.img_path.setReadOnly(True)
        if existing and existing.image_data:
            self.img_path.setText("<loaded>")
            self._img_data = existing.image_data
        else:
            self._img_data = ""
        browse = QPushButton("Browse")
        browse.setStyleSheet(f"background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 8px; padding: 6px 12px;")
        browse.clicked.connect(self._browse_image)
        img_row.addWidget(self.img_path, stretch=1)
        img_row.addWidget(browse)
        lo.addLayout(img_row)

        # Similarity
        sim_row = QHBoxLayout()
        sim_row.addWidget(QLabel("Similarity"))
        self.sim = QLineEdit(str(getattr(existing, 'similarity', 0.8)) if existing else "0.8")
        self.sim.setFixedWidth(60)
        sim_row.addWidget(self.sim)
        sim_row.addStretch()
        lo.addLayout(sim_row)

        # Wait timeout
        wait_row = QHBoxLayout()
        wait_row.addWidget(QLabel("Wait timeout (s)"))
        self.wait = QLineEdit(str(getattr(existing, 'wait_timeout', 10.0)) if existing else "10.0")
        self.wait.setFixedWidth(60)
        wait_row.addWidget(self.wait)
        wait_row.addStretch()
        lo.addLayout(wait_row)

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
        ok = QPushButton("Add Image")
        ok.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {C['accent']},stop:1 {C['accent_secondary']}); color: {C['text_inverse']}; border: none; border-radius: 10px; padding: 8px 16px; font-weight: 700;")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        lo.addLayout(btn_row)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            try:
                with open(path, "rb") as f:
                    self._img_data = base64.b64encode(f.read()).decode()
                self.img_path.setText(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def get_action(self):
        try:
            sim = float(self.sim.text())
            wait = float(self.wait.text())
        except ValueError:
            return None
        if not self._img_data:
            QMessageBox.warning(self, "No Image", "Please select an image.")
            return None
        return Action(
            key="[IMAGE]",
            duration=0.05,
            action_type="image",
            image_data=self._img_data,
            similarity=sim,
            wait_timeout=wait,
            label=self.lbl.text().strip()
        )
