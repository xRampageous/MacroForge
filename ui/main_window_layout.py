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

    # Left command rail.
    sidebar = QFrame()
    sidebar.setObjectName("mf3_sidebar")
    sidebar.setFixedWidth(220)
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
    add_lo.setContentsMargins(12, 10, 12, 12)
    add_lo.setSpacing(9)
    add_lo.addLayout(section_header("ADD ACTION", "bolt", C["accent"]))
    add_grid = QGridLayout()
    add_grid.setContentsMargins(0, 0, 0, 0)
    add_grid.setHorizontalSpacing(8)
    add_grid.setVerticalSpacing(8)
    action_specs = [
        ("Key", self._open_key_dialog, C["key"], "key", 0, 0, 1, 1),
        ("Click", self._open_click_dialog, C["click"], "click", 0, 1, 1, 1),
        ("Delay", self._open_pause_dialog, C["pause"], "delay", 1, 0, 1, 1),
        ("Image", self._open_image_dialog, C["image"], "image", 1, 1, 1, 1),
        ("Condition", self._open_condition_dialog, C["condition"], "condition", 2, 0, 1, 1),
        ("Loop", self._open_loop_dialog, C["loop"], "loop", 2, 1, 1, 1),
        ("Group", self._open_group_dialog, C["group"], "folder", 3, 0, 1, 2),
    ]
    for text, callback, color, icon_name, row, col, rowspan, colspan in action_specs:
        btn = self._add_btn(text, callback, color, None, icon_name)
        btn.setFixedHeight(54)
        btn.setIconSize(QSize(19, 19))
        add_grid.addWidget(btn, row, col, rowspan, colspan)
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
    selector_row.addWidget(self.inspector_selector, stretch=1)
    more_btn = QPushButton()
    more_btn.setObjectName("icon_btn")
    more_btn.setFixedSize(30, 30)
    more_btn.setIcon(icon("menu", 14, C["text_dim"]))
    selector_row.addWidget(more_btn)
    insp_lo.addLayout(selector_row)

    preview = QFrame()
    preview.setObjectName("inspector_preview")
    preview.setFixedHeight(118)
    preview.setStyleSheet(
        f"QFrame#inspector_preview {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #06182A, stop:1 {C['bg_secondary']}); border: 1px solid {C['border']}; "
        "border-radius: 9px; }}"
    )
    preview_lo = QVBoxLayout(preview)
    preview_lo.setContentsMargins(8, 8, 8, 8)
    preview_lo.setSpacing(3)
    preview_icon = QLabel()
    preview_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview_icon.setPixmap(icon("image", 50, C["image"]).pixmap(50, 50))
    preview_lo.addWidget(preview_icon, stretch=1)
    preview_text = QLabel("Image/action preview")
    preview_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview_text.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
    preview_lo.addWidget(preview_text)
    insp_lo.addWidget(preview)

    toolbar = QHBoxLayout()
    toolbar.setContentsMargins(0, 0, 0, 0)
    toolbar.setSpacing(5)
    for name, slot, tip, clr in [
        ("check", self._apply_inspector, "Apply", C["success"]),
        ("play", self.test_selected_action, "Test selected action", C["success"]),
        ("cross", self._cancel_inspector, "Cancel", C["error"]),
        ("trash", lambda: self.delete_action(self.active_index), "Delete", C["error"]),
        ("duplicate", self._duplicate_inspector, "Duplicate", C["accent"]),
        ("edit", self._open_active_dialog, "Edit", C["accent"]),
    ]:
        btn = QPushButton()
        btn.setObjectName("icon_btn")
        btn.setIcon(icon(name, 14, clr))
        btn.setToolTip(tip)
        btn.setFixedSize(30, 30)
        if slot:
            btn.clicked.connect(slot)
        toolbar.addWidget(btn)
    toolbar.addStretch()
    insp_lo.addLayout(toolbar)

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
    ik_lo = QVBoxLayout(self.insp_key)
    ik_lo.setContentsMargins(0, 0, 0, 0)
    ik_lo.setSpacing(4)
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

    self.insp_pause = QWidget()
    ip_lo = QVBoxLayout(self.insp_pause)
    ip_lo.setContentsMargins(0, 0, 0, 0)
    ip_lo.setSpacing(4)
    self.ip_dur = form_input("duration")
    self.ip_label = form_input("label")
    ip_lo.addWidget(form_label("Duration"))
    ip_lo.addWidget(self.ip_dur)
    ip_lo.addWidget(form_label("Label"))
    ip_lo.addWidget(self.ip_label)

    self.insp_click = QWidget()
    ic_lo = QVBoxLayout(self.insp_click)
    ic_lo.setContentsMargins(0, 0, 0, 0)
    ic_lo.setSpacing(4)
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

    self.insp_image = QWidget()
    ii_lo = QVBoxLayout(self.insp_image)
    ii_lo.setContentsMargins(0, 0, 0, 0)
    ii_lo.setSpacing(4)
    self.ii_sim = form_input("similarity", "0.8")
    self.ii_wait = form_input("wait timeout", "10.0")
    self.ii_retry_count = QSpinBox()
    self.ii_retry_count.setRange(1, 99)
    self.ii_retry_count.setFixedHeight(30)
    self.ii_retry_delay = form_input("delay", "0.25")
    self.ii_fail_mode = compact_combo(["default", "continue", "stop", "jump", "recovery_group"])
    self.ii_fail_target = compact_combo()
    retry_row = QHBoxLayout()
    retry_row.setSpacing(5)
    retry_row.addWidget(self.ii_retry_count)
    retry_row.addWidget(self.ii_retry_delay)
    for label, widget in [
        ("MATCHING - Similarity", self.ii_sim),
        ("Wait timeout", self.ii_wait),
    ]:
        ii_lo.addWidget(form_label(label))
        ii_lo.addWidget(widget)
    ii_lo.addWidget(form_label("RETRY - attempts / delay"))
    ii_lo.addLayout(retry_row)
    ii_lo.addWidget(form_label("ON FAIL"))
    ii_lo.addWidget(self.ii_fail_mode)
    ii_lo.addWidget(form_label("FAIL TARGET"))
    ii_lo.addWidget(self.ii_fail_target)

    self.insp_group = QWidget()
    ig_lo = QVBoxLayout(self.insp_group)
    ig_lo.setContentsMargins(0, 0, 0, 0)
    ig_lo.setSpacing(4)
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

    self.insp_loop = QWidget()
    il_lo = QVBoxLayout(self.insp_loop)
    il_lo.setContentsMargins(0, 0, 0, 0)
    il_lo.setSpacing(4)
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

    self.insp_condition = QWidget()
    ico_lo = QVBoxLayout(self.insp_condition)
    ico_lo.setContentsMargins(0, 0, 0, 0)
    ico_lo.setSpacing(4)
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
    self.tl_filter.setFixedSize(52, 32)
    self.tl_filter.setToolTip("Quick timeline filter")
    self.tl_filter.currentTextChanged.connect(lambda t: self.timeline.set_quick_filter(t))
    dock_lo.addWidget(self.tl_filter)

    self.tl_search = QLineEdit()
    self.tl_search.setPlaceholderText("Search...")
    self.tl_search.setClearButtonEnabled(True)
    self.tl_search.setMinimumWidth(70)
    self.tl_search.setMaximumWidth(100)
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
    self.profile_btn.setFixedSize(112, 32)
    self.profile_btn.clicked.connect(self._show_profile_menu)
    dock_lo.addWidget(self.profile_btn)

    self.update_top_btn = header_icon_button("update_top_btn", "update", C["accent"], "Check for updates", self._check_update_manual)
    dock_lo.addWidget(self.update_top_btn)

    self.menu_top_btn = header_icon_button("menu_top_btn", "menu", C["text_dim"], "Menu", self._show_action_menu)
    dock_lo.addWidget(self.menu_top_btn)

    status_pill = QFrame()
    status_pill.setObjectName("status_pill")
    status_pill.setMinimumWidth(120)
    status_pill.setMaximumWidth(150)
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
