"""Image search action dialog — comprehensive PyQt6 rebuild with all v1.1.0 fields."""
import base64
import io
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QComboBox, QCheckBox,
    QFrame, QSpinBox, QWidget, QApplication
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QCursor
from models import Action
from ui.theme import COLORS


def _section(title, color, layout):
    lbl = QLabel(title)
    lbl.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: bold; letter-spacing: 1.5px;")
    layout.addWidget(lbl)


def _field_row(label, widget, lo, hint=None):
    row = QHBoxLayout()
    row.setSpacing(6)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; min-width: 90px;")
    row.addWidget(lbl)
    row.addWidget(widget)
    if hint:
        h = QLabel(hint)
        h.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 10px;")
        row.addWidget(h)
    row.addStretch()
    lo.addLayout(row)


class CaptureOverlay(QWidget):
    """Fullscreen overlay for selecting a screen region to capture."""
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        # Cover all screens
        geo = QApplication.primaryScreen().geometry()
        for scr in QApplication.screens():
            geo = geo.united(scr.geometry())
        self.setGeometry(geo)
        self._start = None
        self._end = None
        self._dragging = False
        self.region = None
        self._closed = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        if self._start and self._end:
            r = QRect(self._start, self._end).normalized()
            painter.setPen(QPen(QColor(COLORS["accent"]), 2))
            painter.setBrush(QColor(56, 180, 255, 40))
            painter.drawRect(r)
            # Draw size label
            painter.setPen(QColor("white"))
            br = r.bottomRight()
            painter.drawText(br.x() + 4, br.y() + 14, f"{r.width()}x{r.height()}")
        painter.end()

    def mousePressEvent(self, event):
        self._start = event.pos()
        self._end = event.pos()
        self._dragging = True
        self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._end = event.pos()
        r = QRect(self._start, self._end).normalized()
        if r.width() > 2 and r.height() > 2:
            self.region = (r.left(), r.top(), r.width(), r.height())
        self._do_close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.region = None
            self._do_close()

    def _do_close(self):
        if not self._closed:
            self._closed = True
            self.close()


class ImageDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Image Search Action")
        self.setMinimumWidth(480)
        C = COLORS
        self.setStyleSheet(f"""
            QDialog {{ background-color: {C['bg']}; }}
            QLabel {{ color: {C['text_dim']}; font-size: 12px; }}
            QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; font-size: 12px; }}
            QLineEdit:focus {{ border-color: {C['accent']}; }}
            QComboBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 4px 8px; font-size: 12px; min-width: 120px; }}
            QCheckBox {{ color: {C['text_dim']}; font-size: 11px; spacing: 4px; }}
        """)

        lo = QVBoxLayout(self)
        lo.setSpacing(8)
        lo.setContentsMargins(14, 14, 14, 14)

        # ── IMAGE ──
        _section("IMAGE", C['accent'], lo)
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
        browse.setObjectName("compact")
        browse.clicked.connect(self._browse_image)
        capture = QPushButton("Capture")
        capture.setObjectName("compact")
        capture.clicked.connect(self._capture_image)
        img_row.addWidget(self.img_path, stretch=1)
        img_row.addWidget(browse)
        img_row.addWidget(capture)
        lo.addLayout(img_row)

        # Preview
        self._preview = QLabel()
        self._preview.setFixedHeight(80)
        self._preview.setStyleSheet(f"background-color: {C['bg_tertiary']}; border-radius: 6px;")
        self._preview.setScaledContents(True)
        lo.addWidget(self._preview)

        # Extra templates (OR match)
        self.extra_tmpl = QLineEdit(getattr(existing, 'extra_images', '') if existing else '')
        self.extra_tmpl.setPlaceholderText("Extra template IDs (pipe-separated)")
        _field_row("Extra templates", self.extra_tmpl, lo, "OR match")

        # ── DETECTION ──
        _section("DETECTION", C['accent'], lo)
        self.sim = QLineEdit(str(getattr(existing, 'similarity', 0.8)) if existing else "0.8")
        self.sim.setFixedWidth(60)
        _field_row("Similarity", self.sim, lo, "0.0–1.0")

        self.wait = QLineEdit(str(getattr(existing, 'wait_timeout', 10.0)) if existing else "10.0")
        self.wait.setFixedWidth(60)
        _field_row("Wait timeout (s)", self.wait, lo)

        self.region = QLineEdit(getattr(existing, 'search_region', '') if existing else '')
        self.region.setPlaceholderText("x,y,w,h  (blank = full screen)")
        _field_row("Search region", self.region, lo)

        self.fg_only = QCheckBox("Foreground window only")
        self.fg_only.setChecked(getattr(existing, 'search_region', '') == 'foreground' if existing else False)
        lo.addWidget(self.fg_only)

        # ── ON MATCH ──
        _section("ON MATCH", C['success'], lo)
        self.on_found = QComboBox()
        self.on_found.addItems(["continue", "click", "double_click", "move_to", "press_key"])
        self.on_found.setCurrentText(getattr(existing, 'on_found_action', 'continue') if existing else 'continue')
        _field_row("Action", self.on_found, lo)

        self.found_key = QLineEdit(getattr(existing, 'on_found_key', '') if existing else '')
        self.found_key.setPlaceholderText("Key to press (if 'press_key')")
        _field_row("Key", self.found_key, lo)

        off = QHBoxLayout()
        self.off_x = QLineEdit(str(getattr(existing, 'click_offset_x', 0)) if existing else "0")
        self.off_x.setFixedWidth(50)
        self.off_y = QLineEdit(str(getattr(existing, 'click_offset_y', 0)) if existing else "0")
        self.off_y.setFixedWidth(50)
        off.addWidget(QLabel("Click offset"))
        off.addWidget(self.off_x)
        off.addWidget(QLabel(","))
        off.addWidget(self.off_y)
        off.addStretch()
        lo.addLayout(off)

        chk = QHBoxLayout()
        self.rand_click = QCheckBox("Random click")
        self.rand_click.setChecked(getattr(existing, 'random_click', False) if existing else False)
        self.pos_mouse = QCheckBox("Position mouse")
        self.pos_mouse.setChecked(getattr(existing, 'position_mouse', False) if existing else False)
        self.loop_found = QCheckBox("Loop until found")
        self.loop_found.setChecked(getattr(existing, 'loop_until_found', False) if existing else False)
        chk.addWidget(self.rand_click)
        chk.addWidget(self.pos_mouse)
        chk.addWidget(self.loop_found)
        chk.addStretch()
        lo.addLayout(chk)

        # ── ON NOT FOUND ──
        _section("ON NOT FOUND", C['error'], lo)
        self.on_miss = QComboBox()
        self.on_miss.addItems(["skip", "stop", "warn"])
        self.on_miss.setCurrentText(getattr(existing, 'on_not_found', 'skip') if existing else 'skip')
        _field_row("Action", self.on_miss, lo)

        jump = QHBoxLayout()
        self.jump_found = QSpinBox()
        self.jump_found.setRange(-1, 999)
        self.jump_found.setValue(getattr(existing, 'jump_to_on_found', -1) if existing else -1)
        self.jump_found.setSpecialValueText("None")
        self.jump_miss = QSpinBox()
        self.jump_miss.setRange(-1, 999)
        self.jump_miss.setValue(getattr(existing, 'jump_to_on_not_found', -1) if existing else -1)
        self.jump_miss.setSpecialValueText("None")
        jump.addWidget(QLabel("Jump on found"))
        jump.addWidget(self.jump_found)
        jump.addWidget(QLabel("Jump on miss"))
        jump.addWidget(self.jump_miss)
        jump.addStretch()
        lo.addLayout(jump)

        # ── LABEL / REPEAT ──
        rep_lbl = QHBoxLayout()
        self.repeat = QLineEdit(str(getattr(existing, 'repeat_count', 1)) if existing else "1")
        self.repeat.setFixedWidth(40)
        rep_lbl.addWidget(QLabel("Repeat"))
        rep_lbl.addWidget(self.repeat)
        rep_lbl.addStretch()
        lo.addLayout(rep_lbl)

        self.lbl = QLineEdit(getattr(existing, 'label', '') if existing else '')
        _field_row("Label", self.lbl, lo)

        lo.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("compact")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Add Image")
        ok.setObjectName("accent")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        lo.addLayout(btn_row)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            try:
                with open(path, "rb") as f:
                    data = f.read()
                self._img_data = base64.b64encode(data).decode()
                self.img_path.setText(path)
                pm = QPixmap()
                pm.loadFromData(data)
                if not pm.isNull():
                    self._preview.setPixmap(pm.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation))
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _capture_image(self):
        try:
            from PIL import ImageGrab
        except ImportError:
            QMessageBox.warning(self, "Missing Dependency", "Screen capture requires Pillow:\npip install pillow")
            return
        self.hide()
        QApplication.processEvents()
        import time
        time.sleep(0.3)
        overlay = CaptureOverlay()
        overlay.showFullScreen()
        overlay.raise_()
        overlay.activateWindow()
        # Run a local event loop until overlay closes
        while not overlay._closed:
            QApplication.processEvents()
            time.sleep(0.02)
        self.show()
        self.raise_()
        self.activateWindow()
        if overlay.region:
            x, y, w, h = overlay.region
            try:
                shot = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
                buf = io.BytesIO()
                shot.save(buf, format="PNG")
                self._img_data = base64.b64encode(buf.getvalue()).decode()
                self.img_path.setText(f"Captured {w}x{h}")
                pm = QPixmap()
                pm.loadFromData(buf.getvalue())
                if not pm.isNull():
                    self._preview.setPixmap(pm.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation))
            except Exception as e:
                QMessageBox.critical(self, "Capture Error", str(e))

    def get_action(self):
        try:
            sim = float(self.sim.text())
            wait = float(self.wait.text())
            off_x = int(self.off_x.text())
            off_y = int(self.off_y.text())
            repeat = int(self.repeat.text())
        except ValueError:
            return None
        if not self._img_data:
            QMessageBox.warning(self, "No Image", "Please select or capture an image.")
            return None
        region = self.region.text().strip()
        if self.fg_only.isChecked():
            region = "foreground"
        return Action(
            key="[IMAGE]",
            duration=0.05,
            action_type="image",
            image_data=self._img_data,
            extra_images=self.extra_tmpl.text().strip(),
            similarity=sim,
            wait_timeout=wait,
            search_region=region,
            on_not_found=self.on_miss.currentText(),
            on_found_action=self.on_found.currentText(),
            on_found_key=self.found_key.text().strip(),
            click_offset_x=off_x,
            click_offset_y=off_y,
            random_click=self.rand_click.isChecked(),
            position_mouse=self.pos_mouse.isChecked(),
            loop_until_found=self.loop_found.isChecked(),
            jump_to_on_found=self.jump_found.value(),
            jump_to_on_not_found=self.jump_miss.value(),
            repeat_count=repeat,
            label=self.lbl.text().strip()
        )
