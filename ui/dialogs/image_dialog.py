"""Image search action dialog — comprehensive PyQt6 rebuild with all v1.1.0 fields."""
import base64
import io
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QComboBox, QCheckBox,
    QFrame, QSpinBox, QWidget, QApplication, QGridLayout,
    QScrollArea, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QCursor
from models import Action
from ui.theme import COLORS


def _hsep(color):
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background-color: {color};")
    return f


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
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        # Use primary screen for capture
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        self._start = None
        self._end = None
        self._dragging = False
        self.region = None
        self._closed = False
        self.setMouseTracking(True)

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
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._end = event.position().toPoint()
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
            self.deleteLater()


class ImageDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Image Search Action")
        self.setMinimumWidth(560)
        C = COLORS
        self._accent = C['image']
        from ui.dialogs._common import dialog_stylesheet, make_header
        self.setStyleSheet(dialog_stylesheet(self._accent))

        lo = QVBoxLayout(self)
        lo.setSpacing(8)
        lo.setContentsMargins(14, 14, 14, 14)

        lo.addWidget(make_header("Image Search", self._accent, "image", "Find an image on screen and react"))

        # ── IMAGE ──
        _section("IMAGE", self._accent, lo)
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
        self._preview.setFixedHeight(120)
        self._preview.setStyleSheet(f"background-color: {C['bg_tertiary']}; border-radius: 6px;")
        self._preview.setScaledContents(True)
        lo.addWidget(self._preview)

        # ── EXTRA TEMPLATES (OR match) ──
        _section("ADDITIONAL TEMPLATES  (OR match)", "#a78bfa", lo)
        extra_card = QFrame()
        extra_card.setStyleSheet(f"background-color: {C['bg_tertiary']}; border-radius: 6px;")
        extra_lo = QHBoxLayout(extra_card)
        extra_lo.setContentsMargins(6, 6, 6, 6)
        extra_lo.setSpacing(6)
        self._extra_scroll = QScrollArea()
        self._extra_scroll.setWidgetResizable(True)
        self._extra_scroll.setFixedHeight(66)
        self._extra_scroll.setStyleSheet("border: none; background: transparent;")
        self._extra_container = QWidget()
        self._extra_flow = QHBoxLayout(self._extra_container)
        self._extra_flow.setSpacing(6)
        self._extra_flow.setContentsMargins(4, 4, 4, 4)
        self._extra_flow.addStretch()
        self._extra_scroll.setWidget(self._extra_container)
        extra_lo.addWidget(self._extra_scroll, stretch=1)
        add_extra = QPushButton("+ Capture extra")
        add_extra.setObjectName("compact")
        add_extra.clicked.connect(self._capture_extra)
        extra_lo.addWidget(add_extra)
        lo.addWidget(extra_card)
        self._extra_list = []
        self._extra_photos = []
        if existing and existing.extra_images:
            for b64 in [x for x in existing.extra_images.split("|") if x]:
                self._add_extra_thumb(b64)

        # ── DETECTION ──
        det_frame = QFrame()
        det_lo = QHBoxLayout(det_frame)
        det_lo.setSpacing(12)
        det_lo.setContentsMargins(0, 0, 0, 0)

        # Left: Match Settings
        lcard = QFrame()
        lcard.setStyleSheet(f"background-color: {C['bg_tertiary']}; border-radius: 8px;")
        llo = QVBoxLayout(lcard)
        llo.setContentsMargins(10, 8, 10, 8)
        llo.setSpacing(6)
        _section("MATCH SETTINGS", "#f59e0b", llo)

        # Similarity as percentage (v1.1.0 style)
        sim_pct = int(round((1.0 - float(getattr(existing, 'similarity', 0.95))) * 100)) if existing else 5
        sim_row = QHBoxLayout()
        sim_row.addWidget(QLabel("Similarity"))
        self.sim_pct = QSpinBox()
        self.sim_pct.setRange(0, 100)
        self.sim_pct.setValue(sim_pct)
        self.sim_pct.setFixedWidth(55)
        sim_row.addWidget(self.sim_pct)
        sim_row.addWidget(QLabel("%  (5 = recommended)"))
        sim_row.addStretch()
        llo.addLayout(sim_row)

        llo.addWidget(_hsep(C['border']))

        # Search region radios
        reg_lbl = QLabel("Search Region:")
        reg_lbl.setStyleSheet(f"color: {C['text']}; font-size: 11px; font-weight: bold;")
        llo.addWidget(reg_lbl)
        self._reg_group = QButtonGroup(self)
        self.reg_whole = QRadioButton("Whole screen")
        self.reg_fg = QRadioButton("Foreground window only")
        self.reg_region = QRadioButton("Specific region:")
        for rb in (self.reg_whole, self.reg_fg, self.reg_region):
            self._reg_group.addButton(rb)
            llo.addWidget(rb)
        _rinit = getattr(existing, 'search_region', '') if existing else ''
        if _rinit == 'foreground':
            self.reg_fg.setChecked(True)
        elif _rinit and ',' in _rinit:
            self.reg_region.setChecked(True)
        else:
            self.reg_whole.setChecked(True)
        _parts = _rinit.split(",") if _rinit and ',' in _rinit else ["0","0","0","0"]
        _parts += ["0"] * (4 - len(_parts))
        reg_f = QHBoxLayout()
        self.reg_x = QLineEdit(_parts[0]); self.reg_x.setFixedWidth(45)
        self.reg_y = QLineEdit(_parts[1]); self.reg_y.setFixedWidth(45)
        self.reg_w = QLineEdit(_parts[2]); self.reg_w.setFixedWidth(45)
        self.reg_h = QLineEdit(_parts[3]); self.reg_h.setFixedWidth(45)
        for lbl, w in [("L:", self.reg_x), ("T:", self.reg_y), ("W:", self.reg_w), ("H:", self.reg_h)]:
            reg_f.addWidget(QLabel(lbl))
            reg_f.addWidget(w)
        rcap = QPushButton("Capture")
        rcap.setObjectName("compact")
        rcap.clicked.connect(self._capture_region)
        reg_f.addWidget(rcap)
        reg_f.addStretch()
        llo.addLayout(reg_f)
        llo.addStretch()

        # Right: Behaviour
        rcard = QFrame()
        rcard.setStyleSheet(f"background-color: {C['bg_tertiary']}; border-radius: 8px;")
        rlo = QVBoxLayout(rcard)
        rlo.setContentsMargins(10, 8, 10, 8)
        rlo.setSpacing(6)
        _section("BEHAVIOUR", C['accent'], rlo)

        self.on_found = QComboBox()
        self.on_found.addItems(["continue", "click", "double_click", "move_to", "press_key"])
        self.on_found.setCurrentText(getattr(existing, 'on_found_action', 'continue') if existing else 'continue')
        _field_row("When found", self.on_found, rlo)

        fk_row = QHBoxLayout()
        self.found_key = QLineEdit(getattr(existing, 'on_found_key', '') if existing else '')
        self.found_key.setPlaceholderText("click then press key")
        self.found_key.setReadOnly(True)
        self.found_key.setFixedWidth(120)
        fk_row.addWidget(QLabel("  Key to press"))
        fk_row.addWidget(self.found_key)
        fk_clr = QPushButton("Clear")
        fk_clr.setObjectName("compact")
        fk_clr.clicked.connect(lambda: self.found_key.setText(""))
        fk_row.addWidget(fk_clr)
        fk_row.addStretch()
        rlo.addLayout(fk_row)
        self.found_key.mousePressEvent = lambda e: self._listen_key() if self.on_found.currentText() == "press_key" else None
        self.on_found.currentTextChanged.connect(self._update_key_state)

        rlo.addWidget(_hsep(C['border']))

        self.on_miss = QComboBox()
        self.on_miss.addItems(["skip", "stop", "warn"])
        self.on_miss.setCurrentText(getattr(existing, 'on_not_found', 'skip') if existing else 'skip')
        _field_row("When not found", self.on_miss, rlo)

        self.wait = QLineEdit(str(getattr(existing, 'wait_timeout', 10)) if existing else "10")
        self.wait.setFixedWidth(50)
        _field_row("Wait timeout (s)", self.wait, rlo, "0 = single shot")

        off = QHBoxLayout()
        self.off_x = QLineEdit(str(getattr(existing, 'click_offset_x', 0)) if existing else "0")
        self.off_x.setFixedWidth(50)
        self.off_y = QLineEdit(str(getattr(existing, 'click_offset_y', 0)) if existing else "0")
        self.off_y.setFixedWidth(50)
        off.addWidget(QLabel("Click offset"))
        off.addWidget(QLabel("X:")); off.addWidget(self.off_x)
        off.addWidget(QLabel("Y:")); off.addWidget(self.off_y)
        off.addStretch()
        rlo.addLayout(off)

        rlo.addWidget(_hsep(C['border']))

        self.rand_click = QCheckBox("Random click within match")
        self.rand_click.setChecked(getattr(existing, 'random_click', False) if existing else False)
        self.pos_mouse = QCheckBox("Position mouse on match")
        self.pos_mouse.setChecked(getattr(existing, 'position_mouse', False) if existing else False)
        self.loop_found = QCheckBox("Loop sequence until found")
        self.loop_found.setChecked(getattr(existing, 'loop_until_found', False) if existing else False)
        rlo.addWidget(self.rand_click)
        rlo.addWidget(self.pos_mouse)
        rlo.addWidget(self.loop_found)
        rlo.addStretch()

        det_lo.addWidget(lcard, stretch=1)
        det_lo.addWidget(rcard, stretch=1)
        lo.addWidget(det_frame)

        # ── META ──
        _section("LABEL, REPEAT & JUMP", "#94a3b8", lo)
        meta = QHBoxLayout()
        self.lbl = QLineEdit(getattr(existing, 'label', '') if existing else '')
        self.lbl.setPlaceholderText("Label")
        meta.addWidget(QLabel("Label")); meta.addWidget(self.lbl)
        self.repeat = QLineEdit(str(getattr(existing, 'repeat_count', 1)) if existing else "1")
        self.repeat.setFixedWidth(40)
        meta.addWidget(QLabel("Repeat")); meta.addWidget(self.repeat)
        self.jump_found = QSpinBox()
        self.jump_found.setRange(-1, 999)
        self.jump_found.setValue(getattr(existing, 'jump_to_on_found', -1) if existing else -1)
        self.jump_found.setSpecialValueText("None")
        meta.addWidget(QLabel("Jump found")); meta.addWidget(self.jump_found)
        self.jump_miss = QSpinBox()
        self.jump_miss.setRange(-1, 999)
        self.jump_miss.setValue(getattr(existing, 'jump_to_on_not_found', -1) if existing else -1)
        self.jump_miss.setSpecialValueText("None")
        meta.addWidget(QLabel("Jump miss")); meta.addWidget(self.jump_miss)
        meta.addStretch()
        lo.addLayout(meta)

        lo.addStretch()
        foot = QHBoxLayout()
        foot.addWidget(QLabel("Changes are saved when you click OK"))
        foot.itemAt(0).widget().setStyleSheet(f"color: {C['text_dark']}; font-size: 10px; font-style: italic;")
        foot.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("compact")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Save & Close")
        ok.setObjectName("accent")
        ok.clicked.connect(self.accept)
        foot.addWidget(cancel)
        foot.addWidget(ok)
        lo.addLayout(foot)

        self._update_key_state()

    def _update_key_state(self):
        enabled = self.on_found.currentText() == "press_key"
        self.found_key.setEnabled(enabled)
        self.found_key.setPlaceholderText("click then press key" if enabled else "select 'press_key' first")

    def _listen_key(self):
        self.found_key.setText("press a key...")
        self.found_key.setStyleSheet("color: #4cc4ff;")
        self.grabKeyboard()

    def keyPressEvent(self, event):
        if self.found_key.text() == "press a key...":
            sym = event.key()
            name = event.text().lower()
            if not name:
                _map = {
                    Qt.Key.Key_Return: "enter", Qt.Key.Key_Enter: "enter",
                    Qt.Key.Key_Escape: "esc", Qt.Key.Key_Space: "space",
                    Qt.Key.Key_Backspace: "backspace", Qt.Key.Key_Tab: "tab",
                    Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right",
                    Qt.Key.Key_Up: "up", Qt.Key.Key.Key_Down: "down",
                    Qt.Key.Key_PageUp: "pageup", Qt.Key.Key_PageDown: "pagedown",
                    Qt.Key.Key_Home: "home", Qt.Key.Key_End: "end",
                    Qt.Key.Key_Insert: "insert", Qt.Key.Key_Delete: "delete",
                }
                for k, v in _map.items():
                    if sym == k:
                        name = v
                        break
            self.found_key.setText(name)
            self.found_key.setStyleSheet("")
            self.releaseKeyboard()
            return
        super().keyPressEvent(event)

    def _add_extra_thumb(self, b64):
        self._extra_list.append(b64)
        thumb = QLabel()
        thumb.setFixedSize(50, 38)
        thumb.setStyleSheet(f"background-color: {COLORS['bg_secondary']}; border-radius: 4px;")
        thumb.setScaledContents(True)
        try:
            raw = base64.b64decode(b64)
            pm = QPixmap()
            pm.loadFromData(raw)
            if not pm.isNull():
                thumb.setPixmap(pm.scaledToHeight(38, Qt.TransformationMode.SmoothTransformation))
        except Exception:
            pass
        idx = len(self._extra_list) - 1
        rem = QPushButton("x")
        rem.setObjectName("compact")
        rem.setFixedSize(18, 18)
        rem.clicked.connect(lambda: self._remove_extra(idx))
        w = QFrame()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(2)
        wl.addWidget(thumb, alignment=Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(rem, alignment=Qt.AlignmentFlag.AlignCenter)
        # Insert before the stretch
        self._extra_flow.insertWidget(self._extra_flow.count() - 1, w)

    def _remove_extra(self, index):
        if 0 <= index < len(self._extra_list):
            self._extra_list.pop(index)
        self._rebuild_extra_flow()

    def _rebuild_extra_flow(self):
        while self._extra_flow.count() > 1:
            item = self._extra_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for b64 in self._extra_list:
            self._add_extra_thumb(b64)

    def _capture_extra(self):
        def _after(b64):
            self._add_extra_thumb(b64)
        self._do_capture(_after, "Capture extra template")

    def _capture_region(self):
        def _after(region):
            self.reg_region.setChecked(True)
            x, y, w, h = region
            self.reg_x.setText(str(x)); self.reg_y.setText(str(y))
            self.reg_w.setText(str(w)); self.reg_h.setText(str(h))
        self._do_capture(_after, "Capture search region", return_region=True)

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
                    self._preview.setPixmap(pm.scaledToHeight(120, Qt.TransformationMode.SmoothTransformation))
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _capture_image(self):
        def _after(b64):
            self._img_data = b64
            self.img_path.setText("Captured")
            try:
                raw = base64.b64decode(b64)
                pm = QPixmap()
                pm.loadFromData(raw)
                if not pm.isNull():
                    self._preview.setPixmap(pm.scaledToHeight(120, Qt.TransformationMode.SmoothTransformation))
            except Exception:
                pass
        self._do_capture(_after, "Capture screen region")

    def _do_capture(self, callback, title_text, return_region=False):
        try:
            from PIL import ImageGrab
        except ImportError:
            QMessageBox.warning(self, "Missing Dependency", "Screen capture requires Pillow:\npip install pillow")
            return
        self.hide()
        QApplication.processEvents()
        import time
        time.sleep(0.15)
        overlay = CaptureOverlay()
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()
        while not overlay._closed:
            QApplication.processEvents()
            time.sleep(0.016)
        time.sleep(0.05)
        self.show()
        self.raise_()
        self.activateWindow()
        if overlay.region:
            x, y, w, h = overlay.region
            if return_region:
                callback((x, y, w, h))
                return
            try:
                shot = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
                buf = io.BytesIO()
                shot.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                callback(b64)
            except Exception as e:
                QMessageBox.critical(self, "Capture Error", str(e))

    def get_action(self):
        try:
            sim_pct = max(0, min(100, int(self.sim_pct.value())))
            sim = round(1.0 - sim_pct / 100.0, 4)
            wait = float(self.wait.text())
            off_x = int(self.off_x.text())
            off_y = int(self.off_y.text())
            repeat = int(self.repeat.text())
        except ValueError:
            return None
        if not self._img_data:
            QMessageBox.warning(self, "No Image", "Please select or capture an image.")
            return None
        # Resolve region
        if self.reg_fg.isChecked():
            region = "foreground"
        elif self.reg_region.isChecked():
            region = f"{self.reg_x.text()},{self.reg_y.text()},{self.reg_w.text()},{self.reg_h.text()}"
        else:
            region = ""
        return Action(
            key="[IMAGE]",
            duration=0.05,
            action_type="image",
            image_data=self._img_data,
            extra_images="|".join(self._extra_list),
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
