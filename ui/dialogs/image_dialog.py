"""Image search action dialog — modernised layout matching reference while preserving all fields."""
import base64
import io
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QComboBox, QCheckBox,
    QFrame, QSpinBox, QWidget, QApplication, QGridLayout,
    QScrollArea, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QRect, QEventLoop, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QCursor, QIntValidator
from models import Action
from ui.theme import COLORS
from debugger import logger


def _hsep(color):
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background-color: {color};")
    return f


class CaptureOverlay(QDialog):
    """Fullscreen overlay for selecting a screen region to capture."""
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.virtualGeometry())
        self._start = None
        self._end = None
        self._dragging = False
        self.region = None
        self.setMouseTracking(True)
        
        # Add instruction label
        layout = QVBoxLayout(self)
        layout.addStretch()
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        self.instruction = QLabel("Hold left mouse button and drag to select an area\nPress Esc to cancel")
        self.instruction.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background: rgba(0,0,0,150); padding: 10px; border-radius: 5px;")
        h_layout.addWidget(self.instruction)
        h_layout.addStretch()
        layout.addLayout(h_layout)
        layout.addStretch()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self._start and self._end:
            r = QRect(self._start, self._end).normalized()
            painter.setPen(QPen(QColor(COLORS["accent"]), 2))
            painter.setBrush(QColor(56, 180, 255, 40))
            painter.drawRect(r)
            painter.setPen(QColor("white"))
            br = r.bottomRight()
            painter.drawText(br.x() + 4, br.y() + 14, f"{r.width()}x{r.height()}")
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self._dragging = True
            self.instruction.hide()
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
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.region = None
            self.reject()


class ImageDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Image Search Action")
        self.setMinimumWidth(520)
        self.setMinimumHeight(640)
        C = COLORS
        self._accent = C['image']
        self.setStyleSheet(f"QDialog {{ background-color: {C['bg']}; }}")

        lo = QVBoxLayout(self)
        lo.setSpacing(10)
        lo.setContentsMargins(18, 18, 18, 18)

        # -- Top description --
        desc = QLabel("This command searches for an image on your screen (pixel by pixel).")
        desc.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        desc.setWordWrap(True)
        lo.addWidget(desc)
        lo.addWidget(_hsep(C['border']))

        # -- Image to search for --
        img_lbl = QLabel("Image to search for:")
        img_lbl.setStyleSheet(f"color: {C['text']}; font-size: 12px; font-weight: bold;")
        lo.addWidget(img_lbl)

        img_area = QHBoxLayout()
        img_area.setSpacing(12)

        # Preview box
        preview_card = QFrame()
        preview_card.setFixedSize(120, 120)
        preview_card.setStyleSheet(f"background-color: {C['bg_tertiary']}; border: 1px solid {C['border']}; border-radius: 6px;")
        pv_lo = QVBoxLayout(preview_card)
        pv_lo.setContentsMargins(4, 4, 4, 4)
        self._preview = QLabel("No image")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(f"color: {C['text_dark']}; font-size: 11px; background: transparent;")
        self._preview.setFixedSize(112, 112)
        pv_lo.addWidget(self._preview)
        img_area.addWidget(preview_card)

        # Right side: capture + browse + hint
        img_right = QVBoxLayout()
        img_right.setSpacing(6)
        img_right.setAlignment(Qt.AlignmentFlag.AlignTop)
        cap_row = QHBoxLayout()
        capture_btn = QPushButton("Capture...")
        capture_btn.setObjectName("compact")
        capture_btn.clicked.connect(self._capture_image)
        cap_row.addWidget(capture_btn)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("compact")
        browse_btn.clicked.connect(self._browse_image)
        cap_row.addWidget(browse_btn)
        cap_row.addStretch()
        img_right.addLayout(cap_row)
        hint = QLabel('Click "Capture" then drag to select an area on screen.\nRecommended size: 50x50px or less for best performance.')
        hint.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px;")
        hint.setWordWrap(True)
        img_right.addWidget(hint)
        img_area.addLayout(img_right, stretch=1)
        lo.addLayout(img_area)

        # Hidden path field (preserves data flow)
        self.img_path = QLineEdit()
        self.img_path.setVisible(False)
        if existing and existing.image_data:
            self.img_path.setText("<loaded>")
            self._img_data = existing.image_data
            self._show_preview(existing.image_data)
        else:
            self._img_data = ""

        # -- Extra templates --
        extra_lbl = QLabel("Additional templates (OR match - any will trigger):")
        extra_lbl.setStyleSheet(f"color: {C['text']}; font-size: 12px; font-weight: bold;")
        lo.addWidget(extra_lbl)

        extra_card = QFrame()
        extra_card.setStyleSheet(f"background-color: {C['bg_tertiary']}; border-radius: 6px;")
        extra_lo = QHBoxLayout(extra_card)
        extra_lo.setContentsMargins(8, 8, 8, 8)
        extra_lo.setSpacing(8)
        self._extra_scroll = QScrollArea()
        self._extra_scroll.setWidgetResizable(True)
        self._extra_scroll.setFixedHeight(66)
        self._extra_scroll.setStyleSheet("border: none; background: transparent;")
        self._extra_container = QWidget()
        self._extra_flow = QHBoxLayout(self._extra_container)
        self._extra_flow.setSpacing(6)
        self._extra_flow.setContentsMargins(4, 4, 4, 4)
        self._extra_flow.addStretch()
        no_extra = QLabel("No extra templates")
        no_extra.setStyleSheet(f"color: {C['text_dark']}; font-size: 11px; font-style: italic;")
        self._extra_flow.insertWidget(0, no_extra)
        self._extra_scroll.setWidget(self._extra_container)
        extra_lo.addWidget(self._extra_scroll, stretch=1)
        add_extra = QPushButton("+ Add extra template")
        add_extra.setObjectName("compact")
        add_extra.clicked.connect(self._capture_extra)
        extra_lo.addWidget(add_extra)
        lo.addWidget(extra_card)
        self._extra_list = []
        if existing and existing.extra_images:
            for b64 in [x for x in existing.extra_images.split("|") if x]:
                self._add_extra_thumb(b64)

        lo.addWidget(_hsep(C['border']))

        # -- Similarity --
        sim_row = QHBoxLayout()
        sim_row.setSpacing(8)
        sim_lbl = QLabel("Similarity coefficient")
        sim_lbl.setStyleSheet(f"color: {C['text']}; font-size: 12px; font-weight: bold;")
        sim_row.addWidget(sim_lbl)
        self.sim_pct = QSpinBox()
        self.sim_pct.setRange(0, 100)
        sim_pct_val = int(round((1.0 - float(getattr(existing, 'similarity', 0.95))) * 100)) if existing else 5
        self.sim_pct.setValue(sim_pct_val)
        self.sim_pct.setFixedWidth(55)
        sim_row.addWidget(self.sim_pct)
        sim_note = QLabel('("0" means "identical", and is recommended)')
        sim_note.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px;")
        sim_row.addWidget(sim_note)
        sim_row.addStretch()
        lo.addLayout(sim_row)

        # -- Position mouse --
        self.pos_mouse = QCheckBox("Position mouse on image if found (moves to match before any action)")
        self.pos_mouse.setChecked(getattr(existing, 'position_mouse', False) if existing else False)
        self.pos_mouse.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        lo.addWidget(self.pos_mouse)

        # -- Search region --
        reg_lbl = QLabel("Search region:")
        reg_lbl.setStyleSheet(f"color: {C['text']}; font-size: 12px; font-weight: bold;")
        lo.addWidget(reg_lbl)

        self._reg_group = QButtonGroup(self)
        self.reg_whole = QRadioButton("Search the whole screen")
        self.reg_fg = QRadioButton("Search in foreground window only")
        self.reg_region = QRadioButton("Search specific region:")
        for rb in (self.reg_whole, self.reg_fg, self.reg_region):
            self._reg_group.addButton(rb)
            rb.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
            lo.addWidget(rb)

        _rinit = getattr(existing, 'search_region', '') if existing else ''
        if _rinit == 'foreground':
            self.reg_fg.setChecked(True)
        elif _rinit and ',' in _rinit:
            self.reg_region.setChecked(True)
        else:
            self.reg_whole.setChecked(True)

        _parts = _rinit.split(",") if _rinit and ',' in _rinit else ["0","0","0","0"]
        _parts += ["0"] * (4 - len(_parts))
        reg_grid = QGridLayout()
        reg_grid.setSpacing(6)
        reg_grid.setContentsMargins(24, 0, 0, 0)
        self.reg_x = QLineEdit(_parts[0]); self.reg_x.setFixedWidth(50)
        self.reg_y = QLineEdit(_parts[1]); self.reg_y.setFixedWidth(50)
        self.reg_w = QLineEdit(_parts[2]); self.reg_w.setFixedWidth(50)
        self.reg_h = QLineEdit(_parts[3]); self.reg_h.setFixedWidth(50)
        for le in (self.reg_x, self.reg_y, self.reg_w, self.reg_h):
            le.setStyleSheet(f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 4px; padding: 3px 6px; font-size: 11px; }}")
        reg_grid.addWidget(QLabel("Left:"), 0, 0)
        reg_grid.addWidget(self.reg_x, 0, 1)
        reg_grid.addWidget(QLabel("Top:"), 0, 2)
        reg_grid.addWidget(self.reg_y, 0, 3)
        reg_grid.addWidget(QLabel("Width:"), 0, 4)
        reg_grid.addWidget(self.reg_w, 0, 5)
        reg_grid.addWidget(QLabel("Height:"), 0, 6)
        reg_grid.addWidget(self.reg_h, 0, 7)
        rcap = QPushButton("Capture region")
        rcap.setObjectName("compact")
        rcap.clicked.connect(self._capture_region)
        reg_grid.addWidget(rcap, 0, 8)
        lo.addLayout(reg_grid)

        lo.addWidget(_hsep(C['border']))

        # -- When found / When not found --
        when_row = QHBoxLayout()
        when_row.setSpacing(12)
        wf_col = QVBoxLayout()
        wf_col.setSpacing(4)
        wf_lbl = QLabel("When found:")
        wf_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        wf_col.addWidget(wf_lbl)
        self.on_found = QComboBox()
        self.on_found.addItems(["continue", "click", "double_click", "move_to", "press_key"])
        self.on_found.setCurrentText(getattr(existing, 'on_found_action', 'continue') if existing else 'continue')
        wf_col.addWidget(self.on_found)
        when_row.addLayout(wf_col)

        wnf_col = QVBoxLayout()
        wnf_col.setSpacing(4)
        wnf_lbl = QLabel("When not found:")
        wnf_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        wnf_col.addWidget(wnf_lbl)
        self.on_miss = QComboBox()
        self.on_miss.addItems(["skip", "stop", "warn"])
        self.on_miss.setCurrentText(getattr(existing, 'on_not_found', 'skip') if existing else 'skip')
        wnf_col.addWidget(self.on_miss)
        when_row.addLayout(wnf_col)
        when_row.addStretch()
        lo.addLayout(when_row)

        # -- Key to press --
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_lbl = QLabel("Key to press:")
        key_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        key_row.addWidget(key_lbl)
        self.found_key = QLineEdit(getattr(existing, 'on_found_key', '') if existing else '')
        self.found_key.setPlaceholderText("click field then press any key")
        self.found_key.setReadOnly(True)
        self.found_key.setFixedWidth(140)
        self.found_key.setStyleSheet(f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 4px; padding: 3px 6px; font-size: 11px; }}")
        self.found_key.mousePressEvent = lambda e: self._listen_key() if self.on_found.currentText() == "press_key" else None
        self.on_found.currentTextChanged.connect(self._update_key_state)
        key_row.addWidget(self.found_key)
        key_clr = QPushButton("x")
        key_clr.setObjectName("compact")
        key_clr.setFixedSize(24, 24)
        key_clr.clicked.connect(lambda: self.found_key.setText(""))
        key_row.addWidget(key_clr)
        key_hint = QLabel("click field then press any key")
        key_hint.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px;")
        key_row.addWidget(key_hint)
        key_row.addStretch()
        lo.addLayout(key_row)

        # -- Wait for image --
        wait_row = QHBoxLayout()
        wait_row.setSpacing(8)
        wait_lbl = QLabel("Wait for image:")
        wait_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        wait_row.addWidget(wait_lbl)
        self.wait = QLineEdit(str(getattr(existing, 'wait_timeout', 10)) if existing else "10")
        self.wait.setFixedWidth(50)
        self.wait.setStyleSheet(f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 4px; padding: 3px 6px; font-size: 11px; }}")
        wait_row.addWidget(self.wait)
        wait_unit = QLabel("seconds (0 = single shot, up to 60s polling)")
        wait_unit.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px;")
        wait_row.addWidget(wait_unit)
        wait_row.addStretch()
        lo.addLayout(wait_row)

        # -- Click offset --
        off_row = QHBoxLayout()
        off_row.setSpacing(8)
        off_lbl = QLabel("Click offset:")
        off_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        off_row.addWidget(off_lbl)
        self.off_x = QLineEdit(str(getattr(existing, 'click_offset_x', 0)) if existing else "0")
        self.off_x.setFixedWidth(45)
        self.off_x.setStyleSheet(f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 4px; padding: 3px 6px; font-size: 11px; }}")
        off_row.addWidget(QLabel("X:"))
        off_row.addWidget(self.off_x)
        self.off_y = QLineEdit(str(getattr(existing, 'click_offset_y', 0)) if existing else "0")
        self.off_y.setFixedWidth(45)
        self.off_y.setStyleSheet(f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 4px; padding: 3px 6px; font-size: 11px; }}")
        off_row.addWidget(QLabel("Y:"))
        off_row.addWidget(self.off_y)
        off_hint = QLabel("px offset from match centre")
        off_hint.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px;")
        off_row.addWidget(off_hint)
        off_row.addStretch()
        lo.addLayout(off_row)

        # -- Checkboxes row --
        chk_row = QHBoxLayout()
        chk_row.setSpacing(16)
        self.rand_click = QCheckBox("Random click within match (human-like)")
        self.rand_click.setChecked(getattr(existing, 'random_click', False) if existing else False)
        self.rand_click.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        chk_row.addWidget(self.rand_click)
        self.loop_found = QCheckBox("Loop sequence until found")
        self.loop_found.setChecked(getattr(existing, 'loop_until_found', False) if existing else False)
        self.loop_found.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;")
        chk_row.addWidget(self.loop_found)
        chk_row.addStretch()
        lo.addLayout(chk_row)

        lo.addWidget(_hsep(C['border']))

        # -- Bottom meta row --
        meta = QHBoxLayout()
        meta.setSpacing(12)
        self.lbl = QLineEdit(getattr(existing, 'label', '') if existing else '')
        self.lbl.setPlaceholderText("Label")
        self.lbl.setStyleSheet(f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 4px; padding: 3px 6px; font-size: 11px; }}")
        meta.addWidget(QLabel("Label"))
        meta.addWidget(self.lbl)
        self.repeat = QLineEdit(str(getattr(existing, 'repeat_count', 1)) if existing else "1")
        self.repeat.setFixedWidth(40)
        self.repeat.setStyleSheet(f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 4px; padding: 3px 6px; font-size: 11px; }}")
        meta.addWidget(QLabel("Repeat"))
        meta.addWidget(self.repeat)
        self.jump_found = QSpinBox()
        self.jump_found.setRange(-1, 999)
        self.jump_found.setValue(getattr(existing, 'jump_to_on_found', -1) if existing else -1)
        self.jump_found.setSpecialValueText("None")
        meta.addWidget(QLabel("Jump if found ->"))
        meta.addWidget(self.jump_found)
        self.jump_miss = QSpinBox()
        self.jump_miss.setRange(-1, 999)
        self.jump_miss.setValue(getattr(existing, 'jump_to_on_not_found', -1) if existing else -1)
        self.jump_miss.setSpecialValueText("None")
        meta.addWidget(QLabel("Jump if NOT found ->"))
        meta.addWidget(self.jump_miss)
        meta.addStretch()
        lo.addLayout(meta)

        lo.addStretch()

        # -- Footer buttons --
        foot = QHBoxLayout()
        foot.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("compact")
        cancel.clicked.connect(self._on_cancel_clicked)
        ok = QPushButton("OK")
        ok.setObjectName("accent")
        ok.clicked.connect(self._on_ok_clicked)
        foot.addWidget(cancel)
        foot.addWidget(ok)
        lo.addLayout(foot)

        self._update_key_state()

    def _on_ok_clicked(self):
        logger.debug("ImageDialog._on_ok_clicked")
        self.accept()

    def _on_cancel_clicked(self):
        logger.debug("ImageDialog._on_cancel_clicked")
        self.reject()

    def accept(self):
        logger.debug("ImageDialog.accept: enter")
        try:
            super().accept()
            logger.debug("ImageDialog.accept: super().accept() returned")
        except Exception:
            logger.exception("ImageDialog.accept: exception")

    def reject(self):
        logger.debug("ImageDialog.reject: enter")
        try:
            super().reject()
            logger.debug("ImageDialog.reject: super().reject() returned")
        except Exception:
            logger.exception("ImageDialog.reject: exception")

    def closeEvent(self, event):
        logger.debug(f"ImageDialog.closeEvent: result()={self.result()}")
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        super().closeEvent(event)

    # -- Helpers --
    def _show_preview(self, b64):
        if not b64:
            return
        try:
            raw = base64.b64decode(b64)
            if not raw:
                logger.debug("_show_preview: empty raw data")
                return
            pm = QPixmap()
            if not pm.loadFromData(raw):
                logger.debug("_show_preview: loadFromData failed")
                return
            if pm.isNull() or pm.width() == 0 or pm.height() == 0:
                logger.debug(f"_show_preview: invalid pixmap {pm.width()}x{pm.height()}")
                return
            scaled = pm.scaled(112, 112, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            if scaled.isNull() or scaled.width() == 0 or scaled.height() == 0:
                logger.debug("_show_preview: scaled pixmap invalid")
                return
            logger.debug(f"_show_preview: showing {scaled.width()}x{scaled.height()} pixmap")
            self._preview.setText("")
            self._preview.setPixmap(scaled)
        except Exception:
            logger.exception("_show_preview: exception")

    def _update_key_state(self):
        enabled = self.on_found.currentText() == "press_key"
        self.found_key.setEnabled(enabled)
        self.found_key.setPlaceholderText("click field then press any key" if enabled else "select 'press_key' first")

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
                    Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
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
        # Remove "No extra templates" label if present
        for i in range(self._extra_flow.count()):
            item = self._extra_flow.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                item.widget().deleteLater()
                self._extra_flow.removeItem(item)
                break
        self._extra_flow.insertWidget(self._extra_flow.count() - 1, w)

    def _remove_extra(self, index):
        if 0 <= index < len(self._extra_list):
            self._extra_list.pop(index)
        self._rebuild_extra_flow()

    def _rebuild_extra_flow(self):
        while self._extra_flow.count() > 0:
            item = self._extra_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._extra_list:
            no_extra = QLabel("No extra templates")
            no_extra.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 11px; font-style: italic;")
            self._extra_flow.addWidget(no_extra)
        else:
            for b64 in self._extra_list:
                self._add_extra_thumb(b64)
        self._extra_flow.addStretch()

    def _capture_extra(self):
        b64 = self._do_capture("Capture extra template")
        if not b64:
            return
        self._add_extra_thumb(b64)

    def _capture_region(self):
        region = self._do_capture("Capture search region", return_region=True)
        if region:
            self.reg_region.setChecked(True)
            x, y, w, h = region
            self.reg_x.setText(str(x)); self.reg_y.setText(str(y))
            self.reg_w.setText(str(w)); self.reg_h.setText(str(h))

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            try:
                with open(path, "rb") as f:
                    data = f.read()
                self._img_data = base64.b64encode(data).decode()
                self.img_path.setText(path)
                self._show_preview(self._img_data)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _capture_image(self):
        logger.debug("image_dialog._capture_image: start")
        b64 = self._do_capture("Capture screen region")
        print(f"DEBUG: _capture_image got type={type(b64)}, value={b64}")
        if not b64:
            return
        logger.debug("image_dialog._capture_image: got b64")
        self._img_data = b64
        self.img_path.setText("Captured")
        self._show_preview(b64)
        logger.debug("image_dialog._capture_image: preview shown")

    def _do_capture(self, title_text, return_region=False):
        logger.debug(f"image_dialog._do_capture: start (return_region={return_region})")
        try:
            from PIL import ImageGrab
        except ImportError:
            QMessageBox.warning(self, "Missing Dependency", "Screen capture requires Pillow:\npip install pillow")
            return None
        # Hide parent dialog completely (like tkinter withdraw)
        logger.debug("image_dialog._do_capture: hiding dialog")
        self.hide()
        import time
        time.sleep(0.1)
        # Show overlay as modal dialog (like tkinter grab_set)
        overlay = CaptureOverlay()
        logger.debug("image_dialog._do_capture: showing overlay")
        result = overlay.exec()
        logger.debug(f"image_dialog._do_capture: overlay returned result={result}")
        # Capture after overlay closes
        captured_result = None
        if result == QDialog.DialogCode.Accepted and overlay.region:
            x, y, w, h = overlay.region
            logger.debug(f"image_dialog._do_capture: region={x},{y},{w},{h}")
            if return_region:
                captured_result = (x, y, w, h)
                logger.debug(f"image_dialog._do_capture: returning region={captured_result}")
            else:
                try:
                    shot = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
                    buf = io.BytesIO()
                    shot.save(buf, format="PNG")
                    b64 = base64.b64encode(buf.getvalue()).decode()
                    logger.debug(f"image_dialog._do_capture: captured b64 len={len(b64)}")
                    print(f"DEBUG: captured image type={type(b64)}, len={len(b64)}")
                    captured_result = b64
                except Exception as e:
                    logger.exception("image_dialog._do_capture: capture failed")
                    QMessageBox.critical(self, "Capture Error", str(e))
        else:
            logger.debug("image_dialog._do_capture: no region selected or cancelled")
        # Show parent dialog again (like tkinter deiconify)
        logger.debug("image_dialog._do_capture: showing dialog")
        self.show()
        self.raise_()
        self.activateWindow()
        print(f"DEBUG: _do_capture returning type={type(captured_result)}, value={captured_result}")
        return captured_result

    def get_action(self):
        logger.debug("image_dialog.get_action: start")
        try:
            sim_pct = max(0, min(100, int(self.sim_pct.value())))
            sim = round(1.0 - sim_pct / 100.0, 4)
            wait = float(self.wait.text() or "0")
            off_x = int(self.off_x.text() or "0")
            off_y = int(self.off_y.text() or "0")
            repeat = int(self.repeat.text() or "1")
        except ValueError:
            logger.debug("image_dialog.get_action: ValueError -> None")
            return None
        if not self._img_data:
            logger.debug("image_dialog.get_action: no img_data -> None")
            QMessageBox.warning(self, "No Image", "Please select or capture an image.")
            return None
        if self.reg_fg.isChecked():
            region = "foreground"
        elif self.reg_region.isChecked():
            rx = self.reg_x.text() or "0"
            ry = self.reg_y.text() or "0"
            rw = self.reg_w.text() or "0"
            rh = self.reg_h.text() or "0"
            region = f"{rx},{ry},{rw},{rh}"
        else:
            region = ""
        logger.debug(f"image_dialog.get_action: building Action sim={sim} wait={wait} region={region}")
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
