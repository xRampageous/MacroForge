"""Main layout construction for MacroForge main window."""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from version import VERSION
from ui.icons import icon
from ui.status_dot import StatusDot
from ui.theme import COLORS
from ui.timeline import TimelineView


def build_main_layout(window):
    self = window
    C = COLORS

    central = QWidget()
    central.setObjectName("root")
    central.setStyleSheet(
        f"QWidget#root {{ background-color: {C['bg']}; }}"
    )
    self.setCentralWidget(central)

    main_lo = QHBoxLayout(central)
    main_lo.setContentsMargins(0, 0, 0, 0)
    main_lo.setSpacing(0)

    def panel_frame(name, accent=None):
        frame = QFrame()
        frame.setObjectName(name)
        border = accent or C["border"]
        frame.setStyleSheet(
            f"QFrame#{name} {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {C['bg_card']}, stop:1 #00050B); "
            f"border: 1px solid {border}; border-radius: 10px; }}"
        )
        return frame

    def section_header(text, icon_name, color):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        ico = QLabel()
        ico.setPixmap(icon(icon_name, 16, color).pixmap(16, 16))
        ico.setFixedSize(18, 18)
        row.addWidget(ico)
        lbl = QLabel(text)
        lbl.setObjectName("section")
        lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 12px; font-weight: 850; "
            "letter-spacing: 0.7px; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch()
        caret = QLabel("^")
        caret.setStyleSheet(f"color: {C['text_dim']}; font-size: 12px; background: transparent;")
        row.addWidget(caret)
        return row

    def form_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; font-weight: 750; "
            "background: transparent;"
        )
        return lbl

    def form_input(placeholder="", text=""):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        if text:
            inp.setText(text)
        inp.setFixedHeight(30)
        inp.setStyleSheet(
            f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 9px; "
            "font-size: 11px; }}"
            f"QLineEdit:focus {{ border-color: {C['accent']}; }}"
        )
        return inp

    def compact_combo(items=None):
        combo = QComboBox()
        if items:
            combo.addItems(items)
        combo.setFixedHeight(30)
        combo.setStyleSheet(
            f"QComboBox {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 8px; "
            "font-size: 11px; }}"
            "QComboBox::drop-down { border: none; width: 18px; }"
        )
        return combo

    def inspector_group(title, icon_name, color):
        card = QFrame()
        card.setObjectName(f"inspector_group_{title.lower().replace(' ', '_')}")
        card.setStyleSheet(
            f"QFrame#{card.objectName()} {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 #04111D, stop:1 #00060E); border: 1px solid {C['border']}; "
            "border-radius: 8px; }}"
        )
        lo = QVBoxLayout(card)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(7)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        ico = QLabel()
        ico.setPixmap(icon(icon_name, 14, color).pixmap(14, 14))
        ico.setFixedSize(15, 15)
        head.addWidget(ico)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 11px; font-weight: 850; "
            "letter-spacing: 0.35px; background: transparent;"
        )
        head.addWidget(lbl)
        info = QLabel("ⓘ")
        info.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
        head.addWidget(info)
        head.addStretch()
        caret = QLabel("^")
        caret.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; background: transparent;")
        head.addWidget(caret)
        lo.addLayout(head)
        return card, lo

    def inspector_value(text="", width=58):
        inp = QLineEdit(text)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFixedSize(width, 28)
        inp.setStyleSheet(
            f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 2px 6px; "
            "font-size: 11px; font-weight: 750; }}"
            f"QLineEdit:focus {{ border-color: {C['accent']}; }}"
        )
        return inp

    # Left command rail.
    sidebar = QFrame()
    sidebar.setObjectName("mf3_sidebar")
    sidebar.setFixedWidth(260)
    sidebar.setStyleSheet(
        f"QFrame#mf3_sidebar {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #020A13, stop:1 #000309); border-right: 1px solid {C['border']}; }}"
    )
    sb_lo = QVBoxLayout(sidebar)
    sb_lo.setContentsMargins(10, 14, 10, 10)
    sb_lo.setSpacing(8)

    brand_row = QHBoxLayout()
    brand_row.setContentsMargins(0, 0, 0, 0)
    brand = QLabel("MACROFORGE")
    brand.setStyleSheet(
        f"color: {C['text']}; font-size: 20px; font-weight: 900; "
        "letter-spacing: -0.7px; background: transparent;"
    )
    brand_row.addWidget(brand)
    brand_row.addStretch()
    ver = QLabel(VERSION)
    ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ver.setFixedSize(54, 30)
    ver.setStyleSheet(
        f"color: {C['accent']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; "
        "font-size: 12px; font-weight: 900;"
    )
    brand_row.addWidget(ver)
    sb_lo.addLayout(brand_row)

    add_card = panel_frame("add_action_card")
    add_lo = QVBoxLayout(add_card)
    add_lo.setContentsMargins(10, 9, 10, 10)
    add_lo.setSpacing(7)
    add_lo.addLayout(section_header("ADD ACTION", "bolt", C["accent"]))
    add_grid = QGridLayout()
    add_grid.setContentsMargins(0, 0, 0, 0)
    add_grid.setHorizontalSpacing(8)
    add_grid.setVerticalSpacing(9)
    action_specs = [
        ("Key", self._open_key_dialog, C["key"], "key", 0, 0, 1, 1),
        ("Click", self._open_click_dialog, C["click"], "click", 0, 1, 1, 1),
        ("Delay", self._open_pause_dialog, C["pause"], "delay", 1, 0, 1, 1),
        ("Image", self._open_image_dialog, C["image"], "image", 1, 1, 1, 1),
        ("Condition", self._open_condition_dialog, C["condition"], "condition", 2, 0, 1, 1),
        ("Loop", self._open_loop_dialog, C["loop"], "loop", 2, 1, 1, 1),
        ("Group", self._open_group_dialog, C["group"], "group", 3, 0, 1, 2),
    ]
    for text, callback, color, icon_name, row, col, rowspan, colspan in action_specs:
        btn = self._add_btn(text, callback, color, None, icon_name)
        btn.setFixedSize(216 if colspan > 1 else 104, 42)
        add_grid.addWidget(btn, row, col, rowspan, colspan, alignment=Qt.AlignmentFlag.AlignCenter)
    add_lo.addLayout(add_grid)
    sb_lo.addWidget(add_card)

    rec_card = panel_frame("recorder_card")
    rec_lo = QVBoxLayout(rec_card)
    rec_lo.setContentsMargins(12, 10, 12, 12)
    rec_lo.setSpacing(9)
    rec_lo.addLayout(section_header("RECORDER", "record", C["accent"]))
    rec_state = QHBoxLayout()
    rec_state.setContentsMargins(0, 0, 0, 0)
    rec_state.setSpacing(7)
    self.rec_dot = StatusDot()
    self.rec_dot.set_color(C["success"])
    rec_state.addWidget(self.rec_dot)
    self.rec_status = QLabel("IDLE")
    self.rec_status.setStyleSheet(
        f"color: {C['text']}; font-size: 12px; font-weight: 900; background: transparent;"
    )
    rec_state.addWidget(self.rec_status)
    rec_state.addStretch()
    self.rec_time = QLabel("00:00:00")
    self.rec_time.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 800;")
    rec_state.addWidget(self.rec_time)
    self.rec_actions = QLabel("0")
    self.rec_actions.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.rec_actions.setFixedSize(28, 24)
    self.rec_actions.setStyleSheet(
        f"color: {C['text']}; background-color: {C['bg_secondary']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; font-size: 11px;"
    )
    rec_state.addWidget(self.rec_actions)
    rec_lo.addLayout(rec_state)
    rec_buttons = QHBoxLayout()
    rec_buttons.setSpacing(8)
    self.rec_btn = QPushButton("Rec")
    self.rec_btn.setObjectName("rec_round_btn")
    self.rec_btn.setIcon(icon("record", 16, C["error"]))
    self.rec_btn.setIconSize(QSize(16, 16))
    self.rec_btn.setFixedHeight(46)
    self.rec_btn.setToolTip("Record (F7)")
    self.rec_btn.clicked.connect(self._toggle_record)
    self.rec_pause_btn = QPushButton("Pause")
    self.rec_pause_btn.setObjectName("rec_pause_btn")
    self.rec_pause_btn.setIcon(icon("pause", 16, C["text_dim"]))
    self.rec_pause_btn.setIconSize(QSize(16, 16))
    self.rec_pause_btn.setFixedHeight(46)
    self.rec_pause_btn.setToolTip("Pause")
    self.rec_pause_btn.setEnabled(False)
    self.rec_pause_btn.clicked.connect(self._toggle_record_pause)
    rec_buttons.addWidget(self.rec_btn)
    rec_buttons.addWidget(self.rec_pause_btn)
    rec_lo.addLayout(rec_buttons)
    sb_lo.addWidget(rec_card)

    self._recorder["btn"] = self.rec_btn
    self._recorder["pause_btn"] = self.rec_pause_btn
    self._recorder["status_dot"] = self.rec_dot
    self._recorder["status_lbl"] = self.rec_status
    self._recorder["time_lbl"] = self.rec_time
    self._recorder["actions_lbl"] = self.rec_actions

    insp_card = panel_frame("inspector_card")
    insp_lo = QVBoxLayout(insp_card)
    insp_lo.setContentsMargins(12, 10, 12, 12)
    insp_lo.setSpacing(8)
    insp_lo.addLayout(section_header("INSPECTOR", "search", C["accent"]))

    selector_row = QHBoxLayout()
    selector_row.setSpacing(6)
    self.inspector_selector = compact_combo(["Select an action"])
    self.inspector_selector.setEnabled(False)
    self.inspector_selector.setIconSize(QSize(15, 15))
    self.inspector_selector.setStyleSheet(
        f"QComboBox {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 8px; "
        "font-size: 11px; }}"
        "QComboBox::drop-down { border: none; width: 20px; }"
    )
    selector_row.addWidget(self.inspector_selector, stretch=1)
    self.inspector_type_badge = QLabel("IMAGE")
    self.inspector_type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.inspector_type_badge.setFixedSize(46, 24)
    self.inspector_type_badge.setStyleSheet(
        f"color: {C['text_dim']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; "
        "font-size: 10px; font-weight: 850;"
    )
    selector_row.addWidget(self.inspector_type_badge)
    more_btn = QPushButton()
    more_btn.setObjectName("icon_btn")
    more_btn.setFixedSize(24, 30)
    more_btn.setIcon(icon("menu", 14, C["text_dim"]))
    selector_row.addWidget(more_btn)
    insp_lo.addLayout(selector_row)

    self.insp_empty = QLabel("Select an action to inspect")
    self.insp_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.insp_empty.setStyleSheet(
        f"color: {C['text_dark']}; font-size: 10px; padding: 6px; background: transparent;"
    )
    insp_lo.addWidget(self.insp_empty)

    self._insp_lo = QVBoxLayout()
    self._insp_lo.setContentsMargins(0, 0, 0, 0)
    self._insp_lo.setSpacing(6)

    self.insp_key = QWidget()
    ik_outer = QVBoxLayout(self.insp_key)
    ik_outer.setContentsMargins(0, 0, 0, 0)
    ik_outer.setSpacing(6)
    key_card, ik_lo = inspector_group("KEY ACTION", "key", C["key"])
    self.ik_key = form_input("key")
    self.ik_dur = form_input("duration")
    self.ik_hold = QCheckBox("Hold mode")
    self.ik_repeat = form_input("repeat", "1")
    self.ik_label = form_input("label")
    for label, widget in [
        ("Key", self.ik_key),
        ("Duration", self.ik_dur),
        ("Repeat", self.ik_repeat),
        ("Label", self.ik_label),
    ]:
        ik_lo.addWidget(form_label(label))
        ik_lo.addWidget(widget)
    ik_lo.addWidget(self.ik_hold)
    ik_outer.addWidget(key_card)

    self.insp_pause = QWidget()
    ip_outer = QVBoxLayout(self.insp_pause)
    ip_outer.setContentsMargins(0, 0, 0, 0)
    ip_outer.setSpacing(6)
    pause_card, ip_lo = inspector_group("DELAY ACTION", "delay", C["pause"])
    self.ip_dur = form_input("duration")
    self.ip_label = form_input("label")
    ip_lo.addWidget(form_label("Duration"))
    ip_lo.addWidget(self.ip_dur)
    ip_lo.addWidget(form_label("Label"))
    ip_lo.addWidget(self.ip_label)
    ip_outer.addWidget(pause_card)

    self.insp_click = QWidget()
    ic_outer = QVBoxLayout(self.insp_click)
    ic_outer.setContentsMargins(0, 0, 0, 0)
    ic_outer.setSpacing(6)
    click_card, ic_lo = inspector_group("CLICK ACTION", "click", C["click"])
    self.ic_x = form_input("x")
    self.ic_y = form_input("y")
    xy = QHBoxLayout()
    xy.setSpacing(5)
    xy.addWidget(self.ic_x)
    xy.addWidget(self.ic_y)
    self.ic_btn = compact_combo(["left", "right", "middle"])
    self.ic_rand = form_input("rand")
    self.ic_repeat = form_input("repeat", "1")
    self.ic_label = form_input("label")
    ic_lo.addWidget(form_label("X, Y"))
    ic_lo.addLayout(xy)
    for label, widget in [
        ("Button", self.ic_btn),
        ("Randomness", self.ic_rand),
        ("Repeat", self.ic_repeat),
        ("Label", self.ic_label),
    ]:
        ic_lo.addWidget(form_label(label))
        ic_lo.addWidget(widget)
    ic_outer.addWidget(click_card)

    self.insp_image = QWidget()
    ii_lo = QVBoxLayout(self.insp_image)
    ii_lo.setContentsMargins(0, 0, 0, 0)
    ii_lo.setSpacing(7)

    preview = QFrame()
    preview.setObjectName("image_inspector_preview")
    preview.setFixedHeight(150)
    preview.setStyleSheet(
        f"QFrame#image_inspector_preview {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #07182A, stop:1 #020A13); border: 1px solid {C['border']}; "
        "border-radius: 8px; }}"
    )
    preview_lo = QVBoxLayout(preview)
    preview_lo.setContentsMargins(7, 7, 7, 7)
    preview_lo.setSpacing(5)
    art = QFrame()
    art.setObjectName("image_preview_art")
    art.setStyleSheet(
        f"QFrame#image_preview_art {{ background-color: #071525; "
        f"border: 1px solid {C['border']}; border-radius: 7px; }}"
    )
    art_lo = QVBoxLayout(art)
    art_lo.setContentsMargins(0, 0, 0, 0)
    art_lo.setSpacing(0)
    art_icon = QLabel()
    art_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    art_icon.setPixmap(icon("image", 62, C["image"]).pixmap(62, 62))
    art_icon.setProperty("has_template", False)
    self.image_preview_label = art_icon
    art_lo.addWidget(art_icon, stretch=1)
    preview_lo.addWidget(art, stretch=1)

    preview_actions = QHBoxLayout()
    preview_actions.setContentsMargins(0, 0, 0, 0)
    preview_actions.setSpacing(6)
    change_btn = QPushButton("Change Image")
    change_btn.setIcon(icon("edit", 13, C["text_dim"]))
    change_btn.setIconSize(QSize(13, 13))
    change_btn.setFixedHeight(28)
    change_btn.setStyleSheet(
        f"QPushButton {{ color: {C['text']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 6px; padding: 3px 8px; "
        "font-size: 10px; font-weight: 750; text-align: left; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; }}"
    )
    change_btn.clicked.connect(lambda: self._open_active_dialog())
    preview_actions.addWidget(change_btn)
    preview_actions.addStretch()
    for attr, name, tip, slot in (
        ("ii_zoom_btn", "search", "Zoom image", self._zoom_image_preview),
        ("ii_fit_btn", "move", "Fit preview", self._fit_image_preview),
        ("ii_capture_btn", "target", "Capture region", self._capture_active_image_region),
    ):
        btn = QPushButton()
        btn.setObjectName("icon_btn")
        btn.setIcon(icon(name, 13, C["text_dim"]))
        btn.setToolTip(tip)
        btn.setFixedSize(28, 28)
        btn.clicked.connect(slot)
        setattr(self, attr, btn)
        preview_actions.addWidget(btn)
    preview_lo.addLayout(preview_actions)
    ii_lo.addWidget(preview)

    matching, matching_lo = inspector_group("MATCHING", "target", C["accent"])
    sim_row = QHBoxLayout()
    sim_row.setContentsMargins(0, 0, 0, 0)
    sim_lbl = form_label("Similarity  ⓘ")
    sim_row.addWidget(sim_lbl)
    sim_row.addStretch()
    self.ii_sim = inspector_value("0.85", 54)
    sim_row.addWidget(self.ii_sim)
    matching_lo.addLayout(sim_row)
    self.ii_sim_slider = QSlider(Qt.Orientation.Horizontal)
    self.ii_sim_slider.setRange(0, 100)
    self.ii_sim_slider.setValue(85)
    self.ii_sim_slider.setFixedHeight(18)
    self.ii_sim_slider.setStyleSheet(
        f"QSlider::groove:horizontal {{ height: 3px; background: {C['lane']}; border-radius: 2px; }}"
        f"QSlider::sub-page:horizontal {{ background: {C['accent']}; border-radius: 2px; }}"
        f"QSlider::handle:horizontal {{ background: {C['accent']}; width: 10px; height: 10px; "
        "border-radius: 5px; margin: -4px 0; }}"
    )
    self.ii_sim_slider.valueChanged.connect(lambda v: self.ii_sim.setText(f"{v / 100:.2f}"))
    matching_lo.addWidget(self.ii_sim_slider)
    scale_row = QHBoxLayout()
    scale_row.setContentsMargins(0, 0, 0, 0)
    left_scale = QLabel("0.00")
    right_scale = QLabel("1.00")
    for lbl in (left_scale, right_scale):
        lbl.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px; background: transparent;")
    scale_row.addWidget(left_scale)
    scale_row.addStretch()
    scale_row.addWidget(right_scale)
    matching_lo.addLayout(scale_row)
    wait_row = QHBoxLayout()
    wait_row.setContentsMargins(0, 0, 0, 0)
    wait_row.addWidget(form_label("Wait timeout  ⓘ"))
    wait_row.addStretch()
    self.ii_wait = inspector_value("1000", 58)
    wait_row.addWidget(self.ii_wait)
    wait_ms = QLabel("ms")
    wait_ms.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
    wait_row.addWidget(wait_ms)
    matching_lo.addLayout(wait_row)
    ii_lo.addWidget(matching)

    retry, retry_lo = inspector_group("RETRY", "update", C["accent"])
    self.ii_retry_count = QSpinBox()
    self.ii_retry_count.setRange(1, 99)
    self.ii_retry_count.setFixedSize(76, 28)
    self.ii_retry_count.setStyleSheet(
        f"QSpinBox {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 2px 8px; font-size: 11px; }}"
    )
    self.ii_retry_delay = inspector_value("250", 76)
    retry_row = QHBoxLayout()
    retry_row.setContentsMargins(0, 0, 0, 0)
    retry_row.setSpacing(8)
    retry_row.addWidget(form_label("Retry attempts / delay"))
    retry_lo.addLayout(retry_row)
    retry_values = QHBoxLayout()
    retry_values.setContentsMargins(0, 0, 0, 0)
    retry_values.setSpacing(7)
    slash = QLabel("/")
    slash.setAlignment(Qt.AlignmentFlag.AlignCenter)
    slash.setStyleSheet(f"color: {C['text']}; font-size: 12px; background: transparent;")
    retry_values.addWidget(self.ii_retry_count)
    retry_values.addWidget(slash)
    retry_values.addWidget(self.ii_retry_delay)
    retry_values.addWidget(form_label("ms"))
    retry_values.addStretch()
    retry_lo.addLayout(retry_values)
    ii_lo.addWidget(retry)

    on_fail, on_fail_lo = inspector_group("ON FAIL", "condition", C["accent"])
    on_fail_row = QHBoxLayout()
    on_fail_row.setContentsMargins(0, 0, 0, 0)
    on_fail_row.addWidget(form_label("On fail"))
    on_fail_row.addStretch()
    self.ii_fail_mode = compact_combo(["Default", "Continue", "Stop", "Jump", "Recovery Group"])
    self.ii_fail_mode.setFixedWidth(118)
    on_fail_row.addWidget(self.ii_fail_mode)
    on_fail_lo.addLayout(on_fail_row)
    ii_lo.addWidget(on_fail)

    fail_target, fail_target_lo = inspector_group("FAIL TARGET", "target", C["accent"])
    target_row = QHBoxLayout()
    target_row.setContentsMargins(0, 0, 0, 0)
    target_row.addWidget(form_label("Fail target"))
    target_row.addStretch()
    self.ii_fail_target = compact_combo()
    self.ii_fail_target.setFixedWidth(118)
    target_row.addWidget(self.ii_fail_target)
    fail_target_lo.addLayout(target_row)
    ii_lo.addWidget(fail_target)

    self.insp_group = QWidget()
    ig_outer = QVBoxLayout(self.insp_group)
    ig_outer.setContentsMargins(0, 0, 0, 0)
    ig_outer.setSpacing(6)
    group_card, ig_lo = inspector_group("GROUP", "folder", C["group"])
    self.ig_name = form_input("group name")
    self.ig_collapsed = QCheckBox("Collapsed")
    self.ig_recovery = QCheckBox("Recovery group")
    self.ig_meta = QLabel("0 actions - ~0.0s")
    self.ig_meta.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
    ig_lo.addWidget(form_label("Group name"))
    ig_lo.addWidget(self.ig_name)
    ig_lo.addWidget(self.ig_collapsed)
    ig_lo.addWidget(self.ig_recovery)
    ig_lo.addWidget(self.ig_meta)
    ig_outer.addWidget(group_card)

    self.insp_loop = QWidget()
    il_outer = QVBoxLayout(self.insp_loop)
    il_outer.setContentsMargins(0, 0, 0, 0)
    il_outer.setSpacing(6)
    loop_card, il_lo = inspector_group("LOOP", "loop", C["loop"])
    self.il_label = form_input("loop label")
    self.il_count = QSpinBox()
    self.il_count.setRange(2, 9999)
    self.il_count.setFixedHeight(30)
    self.il_target = compact_combo()
    il_lo.addWidget(form_label("Label"))
    il_lo.addWidget(self.il_label)
    il_lo.addWidget(form_label("Repeat count"))
    il_lo.addWidget(self.il_count)
    il_lo.addWidget(form_label("Target"))
    il_lo.addWidget(self.il_target)
    il_outer.addWidget(loop_card)

    self.insp_condition = QWidget()
    ico_outer = QVBoxLayout(self.insp_condition)
    ico_outer.setContentsMargins(0, 0, 0, 0)
    ico_outer.setSpacing(6)
    condition_card, ico_lo = inspector_group("CONDITION", "condition", C["condition"])
    self.ico_label = form_input("condition label")
    self.ico_type = compact_combo(["pixel_color", "variable", "none"])
    self.ico_true = compact_combo()
    self.ico_false = compact_combo()
    self.ico_retry_count = QSpinBox()
    self.ico_retry_count.setRange(1, 99)
    self.ico_retry_count.setFixedHeight(30)
    self.ico_retry_delay = form_input("delay", "0.25")
    self.ico_fail_mode = compact_combo(["default", "continue", "stop", "jump", "recovery_group"])
    self.ico_fail_target = compact_combo()
    self.ico_rule = QLabel("Edit for pixel/variable values")
    self.ico_rule.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
    ico_retry = QHBoxLayout()
    ico_retry.setSpacing(5)
    ico_retry.addWidget(self.ico_retry_count)
    ico_retry.addWidget(self.ico_retry_delay)
    for label, widget in [
        ("Label", self.ico_label),
        ("Type", self.ico_type),
        ("True target", self.ico_true),
        ("False target", self.ico_false),
    ]:
        ico_lo.addWidget(form_label(label))
        ico_lo.addWidget(widget)
    ico_lo.addWidget(form_label("Retry attempts / delay"))
    ico_lo.addLayout(ico_retry)
    ico_lo.addWidget(form_label("On false/fail"))
    ico_lo.addWidget(self.ico_fail_mode)
    ico_lo.addWidget(form_label("Fail target"))
    ico_lo.addWidget(self.ico_fail_target)
    ico_lo.addWidget(self.ico_rule)
    ico_outer.addWidget(condition_card)

    for pane in (
        self.insp_key,
        self.insp_pause,
        self.insp_click,
        self.insp_image,
        self.insp_group,
        self.insp_loop,
        self.insp_condition,
    ):
        pane.setVisible(False)
        self._insp_lo.addWidget(pane)
    insp_lo.addLayout(self._insp_lo)
    insp_lo.addStretch()
    sb_lo.addWidget(insp_card, stretch=1)
    main_lo.addWidget(sidebar)

    # Main workspace.
    content = QFrame()
    content.setObjectName("mf3_content")
    content.setStyleSheet(f"QFrame#mf3_content {{ background-color: {C['bg']}; border: none; }}")
    content_lo = QVBoxLayout(content)
    content_lo.setContentsMargins(0, 0, 0, 0)
    content_lo.setSpacing(0)

    header_shell = QFrame()
    header_shell.setFixedHeight(62)
    header_shell.setStyleSheet(f"background-color: {C['bg']}; border: none;")
    shell_lo = QVBoxLayout(header_shell)
    shell_lo.setContentsMargins(8, 6, 8, 4)
    shell_lo.setSpacing(0)

    header_dock = QFrame()
    header_dock.setObjectName("header_dock")
    header_dock.setStyleSheet(
        f"QFrame#header_dock {{ background-color: {C['bg_card']}; "
        f"border: 1px solid {C['border']}; border-radius: 11px; }}"
    )
    dock_lo = QHBoxLayout(header_dock)
    dock_lo.setContentsMargins(7, 6, 7, 6)
    dock_lo.setSpacing(5)

    def header_icon_button(obj, icon_name, color, tooltip, slot):
        btn = QPushButton()
        btn.setObjectName(obj)
        btn.setIcon(icon(icon_name, 15, color))
        btn.setIconSize(QSize(15, 15))
        btn.setToolTip(tooltip)
        btn.setFixedSize(30, 32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton#{obj} {{ background-color: {C['bg_tertiary']}; color: {color}; "
            f"border: 1px solid {C['border']}; border-radius: 8px; padding: 0; }}"
            f"QPushButton#{obj}:hover {{ border-color: {color}; background-color: {C['bg_hover']}; }}"
            f"QPushButton#{obj}:checked {{ border-color: {color}; background-color: {C['accent_glow']}; }}"
        )
        btn.clicked.connect(slot)
        return btn

    tools = QFrame()
    tools.setObjectName("toolbar_group")
    tools.setStyleSheet(
        f"QFrame#toolbar_group {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; }}"
    )
    tools_lo = QHBoxLayout(tools)
    tools_lo.setContentsMargins(2, 0, 2, 0)
    tools_lo.setSpacing(0)
    self.editor_mode_btn = header_icon_button("editor_mode_btn", "edit", C["accent"], "Open macro editor mode", self.open_macro_editor)
    self.preflight_btn = header_icon_button("preflight_btn", "check", C["success"], "Run macro health / pre-flight checker", self.open_preflight_report)
    self.runtime_log_btn = header_icon_button("runtime_log_btn", "eye", C["pause_cyan"], "Show / hide live runtime log", self.toggle_runtime_log_panel)
    self.runtime_log_btn.setCheckable(True)
    self.compact_view_btn = header_icon_button("view_toggle", "menu", C["accent"], "Timeline list view", lambda: None)
    self.compact_view_btn.setCheckable(True)
    self.compact_view_btn.setChecked(True)
    for btn in (self.editor_mode_btn, self.preflight_btn, self.runtime_log_btn, self.compact_view_btn):
        tools_lo.addWidget(btn)
    dock_lo.addWidget(tools)

    self.tl_filter = QComboBox()
    self.tl_filter.addItems(["All", "Images", "Loops", "Conditions", "Groups", "Warnings", "Current group"])
    self.tl_filter.setFixedSize(48, 32)
    self.tl_filter.setToolTip("Quick timeline filter")
    self.tl_filter.currentTextChanged.connect(lambda t: self.timeline.set_quick_filter(t))
    dock_lo.addWidget(self.tl_filter)

    self.tl_search = QLineEdit()
    self.tl_search.setPlaceholderText("Search...")
    self.tl_search.setClearButtonEnabled(True)
    self.tl_search.setMinimumWidth(52)
    self.tl_search.setMaximumWidth(80)
    self.tl_search.setFixedHeight(32)
    self.tl_search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.tl_search.addAction(icon("search", 15, C["text_dim"]), QLineEdit.ActionPosition.LeadingPosition)
    self.tl_search.textChanged.connect(lambda t: self.timeline.set_search(t))
    dock_lo.addWidget(self.tl_search, stretch=1)

    self.profile_btn = QPushButton("Default Profile")
    self.profile_btn.setObjectName("profile_switcher")
    self.profile_btn.setIcon(icon("folder", 15, C["accent"]))
    self.profile_btn.setIconSize(QSize(15, 15))
    self.profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.profile_btn.setToolTip("Switch profile")
    self.profile_btn.setFixedSize(96, 32)
    self.profile_btn.clicked.connect(self._show_profile_menu)
    dock_lo.addWidget(self.profile_btn)

    self.update_top_btn = header_icon_button("update_top_btn", "update", C["accent"], "Check for updates", self._check_update_manual)
    dock_lo.addWidget(self.update_top_btn)

    self.menu_top_btn = header_icon_button("menu_top_btn", "menu", C["text_dim"], "Menu", self._show_action_menu)
    dock_lo.addWidget(self.menu_top_btn)

    status_pill = QFrame()
    status_pill.setObjectName("status_pill")
    status_pill.setMinimumWidth(100)
    status_pill.setMaximumWidth(130)
    status_pill.setFixedHeight(32)
    status_pill.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    status_pill.setStyleSheet(
        f"QFrame#status_pill {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; }}"
    )
    self.status_pill = status_pill
    sp_lo = QHBoxLayout(status_pill)
    sp_lo.setContentsMargins(8, 0, 8, 0)
    sp_lo.setSpacing(5)
    self.status_dot = StatusDot()
    self.status_dot.set_color(C["success"])
    self.status_dot.setFixedSize(13, 13)
    sp_lo.addWidget(self.status_dot)
    self.status_icon = QLabel()
    self.status_icon.setPixmap(icon("check", 16, C["success"]).pixmap(16, 16))
    self.status_icon.setFixedSize(16, 16)
    self.status_icon.setScaledContents(True)
    self.status_icon.setVisible(False)
    sp_lo.addWidget(self.status_icon)
    self.status_text = QLabel("Ready")
    self.status_text.setStyleSheet(f"color: {C['text']}; font-size: 11px; font-weight: 850;")
    self.status_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.status_text.setWordWrap(False)
    sp_lo.addWidget(self.status_text, stretch=1)
    self.autosave_label = QLabel("Saved")
    self.autosave_label.setObjectName("autosave_label")
    self.autosave_label.setStyleSheet(
        f"QLabel#autosave_label {{ color: {C['success']}; font-size: 10px; "
        f"background-color: {C['bg_card']}; border: 1px solid {C['border']}; "
        "border-radius: 7px; padding: 2px 6px; }}"
    )
    self.autosave_label.setToolTip("Profile autosave state")
    sp_lo.addWidget(self.autosave_label)
    dock_lo.addWidget(status_pill)

    self.macro_summary = QLabel("0 actions - 0 image checks - ~0s")
    self.macro_summary.setVisible(False)
    shell_lo.addWidget(header_dock)
    content_lo.addWidget(header_shell)

    self.timeline = TimelineView(model=self.action_model)
    content_lo.addWidget(self.timeline, stretch=1)

    self.runtime_log_panel = QFrame()
    self.runtime_log_panel.setObjectName("runtime_log_panel")
    self.runtime_log_panel.setFixedHeight(132)
    self.runtime_log_panel.setVisible(False)
    self.runtime_log_panel.setStyleSheet(
        f"QFrame#runtime_log_panel {{ background-color: {C['bg_card']}; "
        f"border-top: 1px solid {C['border']}; border-bottom: 1px solid {C['border']}; }}"
    )
    rlp_lo = QVBoxLayout(self.runtime_log_panel)
    rlp_lo.setContentsMargins(10, 6, 10, 8)
    rlp_lo.setSpacing(5)
    rlp_head = QHBoxLayout()
    rlp_title = QLabel("LIVE RUNTIME LOG")
    rlp_title.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; letter-spacing: 1px;")
    rlp_head.addWidget(rlp_title)
    rlp_head.addStretch()
    clear_log_btn = QPushButton("Clear")
    clear_log_btn.setFixedSize(54, 24)
    clear_log_btn.clicked.connect(self.clear_runtime_log_panel)
    hide_log_btn = QPushButton("Hide")
    hide_log_btn.setFixedSize(50, 24)
    hide_log_btn.clicked.connect(lambda: self.toggle_runtime_log_panel(False))
    rlp_head.addWidget(clear_log_btn)
    rlp_head.addWidget(hide_log_btn)
    rlp_lo.addLayout(rlp_head)
    self.runtime_log_edit = QPlainTextEdit()
    self.runtime_log_edit.setReadOnly(True)
    self.runtime_log_edit.setMaximumBlockCount(600)
    self.runtime_log_edit.setStyleSheet(
        f"QPlainTextEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; padding: 6px; "
        "font-family: Consolas, monospace; font-size: 10px; }}"
    )
    rlp_lo.addWidget(self.runtime_log_edit, stretch=1)
    content_lo.addWidget(self.runtime_log_panel)

    self.playback_panel = self._make_playback_panel()
    content_lo.addWidget(self.playback_panel)
    main_lo.addWidget(content, stretch=1)
