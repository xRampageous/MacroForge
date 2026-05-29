"""Image editor dialog for MacroForge PyQt6."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, QSpinBox,
    QCheckBox, QPushButton, QHBoxLayout, QComboBox, QLineEdit, QLabel,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from ui.theme import COLORS
from models import Action
import base64
import io


class ImageEditorDialog(QDialog):
    """Dialog to edit image search action properties."""

    def __init__(self, parent, action: Action):
        super().__init__(parent)
        self._action = action
        self.setWindowTitle("Edit Image Action")
        self.resize(420, 450)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS['bg']}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        # Image data
        img_row = QHBoxLayout()
        self._lbl_img = QLabel("No image")
        self._lbl_img.setStyleSheet(f"color: {COLORS['text_dim']}; padding: 6px; background-color: {COLORS['bg_tertiary']}; border-radius: 6px;")
        img_row.addWidget(self._lbl_img)
        btn_capture = QPushButton("Capture")
        btn_capture.clicked.connect(self._capture_screenshot)
        img_row.addWidget(btn_capture)
        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self._load_image)
        img_row.addWidget(btn_load)
        form.addRow("Template:", img_row)

        self._spin_sim = QDoubleSpinBox()
        self._spin_sim.setRange(0.0, 1.0)
        self._spin_sim.setSingleStep(0.05)
        self._spin_sim.setDecimals(2)
        self._spin_sim.setValue(getattr(self._action, "similarity", 0.95))
        form.addRow("Similarity:", self._spin_sim)

        self._line_region = QLineEdit()
        self._line_region.setPlaceholderText("x,y,w,h or leave blank for full screen")
        self._line_region.setText(getattr(self._action, "search_region", ""))
        form.addRow("Search region:", self._line_region)

        self._spin_timeout = QDoubleSpinBox()
        self._spin_timeout.setRange(0, 300)
        self._spin_timeout.setSingleStep(0.5)
        self._spin_timeout.setValue(getattr(self._action, "wait_timeout", 0.0))
        form.addRow("Wait timeout (s):", self._spin_timeout)

        self._combo_notfound = QComboBox()
        self._combo_notfound.addItems(["skip", "stop", "warn"])
        self._combo_notfound.setCurrentText(getattr(self._action, "on_not_found", "skip"))
        form.addRow("When not found:", self._combo_notfound)

        self._combo_found = QComboBox()
        self._combo_found.addItems(["continue", "click", "double_click", "press_key", "move_to"])
        self._combo_found.setCurrentText(getattr(self._action, "on_found_action", "continue"))
        form.addRow("When found:", self._combo_found)

        self._line_key = QLineEdit()
        self._line_key.setText(getattr(self._action, "on_found_key", ""))
        form.addRow("On-found key:", self._line_key)

        self._chk_pos = QCheckBox()
        self._chk_pos.setChecked(getattr(self._action, "position_mouse", False))
        form.addRow("Position mouse:", self._chk_pos)

        self._chk_rand = QCheckBox()
        self._chk_rand.setChecked(getattr(self._action, "random_click", False))
        form.addRow("Random click:", self._chk_rand)

        self._chk_loop = QCheckBox()
        self._chk_loop.setChecked(getattr(self._action, "loop_until_found", False))
        form.addRow("Loop until found:", self._chk_loop)

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

        if getattr(self._action, "image_data", ""):
            self._lbl_img.setText("Image loaded ✓")
            self._lbl_img.setStyleSheet(f"color: {COLORS['success']}; padding: 6px; background-color: {COLORS['success_bg']}; border-radius: 6px;")

    def _capture_screenshot(self):
        try:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(0)
                self._lbl_img.setText(f"Screenshot {pixmap.width()}x{pixmap.height()}")
                # Store base64
                buf = io.BytesIO()
                pixmap.toImage().save(buf, "PNG")
                self._action.image_data = base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            QMessageBox.critical(self, "Screenshot Error", str(e))

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Image", "", "Images (*.png *.jpg *.bmp)")
        if path:
            try:
                with open(path, "rb") as f:
                    self._action.image_data = base64.b64encode(f.read()).decode()
                self._lbl_img.setText("Image loaded ✓")
                self._lbl_img.setStyleSheet(f"color: {COLORS['success']}; padding: 6px; background-color: {COLORS['success_bg']}; border-radius: 6px;")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", str(e))

    def _on_ok(self):
        self._action.similarity = self._spin_sim.value()
        self._action.search_region = self._line_region.text()
        self._action.wait_timeout = self._spin_timeout.value()
        self._action.on_not_found = self._combo_notfound.currentText()
        self._action.on_found_action = self._combo_found.currentText()
        self._action.on_found_key = self._line_key.text()
        self._action.position_mouse = self._chk_pos.isChecked()
        self._action.random_click = self._chk_rand.isChecked()
        self._action.loop_until_found = self._chk_loop.isChecked()
        self.accept()
