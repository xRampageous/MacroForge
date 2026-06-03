"""Main layout construction for MacroForge main window."""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
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
    self.setCentralWidget(central)
    main_lo = QHBoxLayout(central)
    main_lo.setContentsMargins(0, 0, 0, 0)
    main_lo.setSpacing(0)

    # ━━ Left sidebar ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    sidebar = QFrame()
    sidebar.setObjectName("glass_card")
    sidebar.setFixedWidth(186)
    sidebar.setStyleSheet(
        f"background-color: {C['bg_card']}; "
        f"border-right: 1px solid {C['border']};"
    )
    sb_lo = QVBoxLayout(sidebar)
    sb_lo.setContentsMargins(16, 18, 12, 12)
    sb_lo.setSpacing(6)

    # Branding + version
    brand_row = QVBoxLayout()
    brand_row.setSpacing(3)
    brand = QLabel("MACROFORGE")
    brand.setObjectName("title")
    brand.setStyleSheet(f"color: {C['text']}; font-size: 16px; font-weight: 600; letter-spacing: -0.3px;")
    brand_row.addWidget(brand)
    ver_lbl = QLabel(VERSION)
    ver_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
    ver_lbl.setStyleSheet(f"color: {C['accent']}; font-size: 11px; font-weight: 600;")
    brand_row.addWidget(ver_lbl)
    sb_lo.addLayout(brand_row)
    sb_lo.addSpacing(16)

    # ── Add Actions ──
    add_lbl = QLabel("ADD ACTION")
    add_lbl.setObjectName("section")
    add_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
    sb_lo.addWidget(add_lbl)
    sb_lo.addSpacing(6)
    self._add_btn("Key", self._open_key_dialog, C["key"], sb_lo, "key")
    self._add_btn("Click", self._open_click_dialog, C["click"], sb_lo, "click")
    self._add_btn("Delay", self._open_pause_dialog, C["pause"], sb_lo, "delay")
    self._add_btn("Image", self._open_image_dialog, C["image"], sb_lo, "image")
    self._add_btn("Condition", self._open_condition_dialog, C["condition"], sb_lo, "condition")
    self._add_btn("Loop", self._open_loop_dialog, C.get("loop", C["success"]), sb_lo, "loop")
    self._add_btn("Group", self._open_group_dialog, C.get("group", C["neon_purple"]), sb_lo, "folder")

    sb_lo.addSpacing(10)

    # ── Recorder ──
    rec_lbl = QLabel("RECORDER  ˅")
    rec_lbl.setObjectName("section")
    rec_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
    sb_lo.addWidget(rec_lbl)
    sb_lo.addSpacing(6)
    rec_card = QFrame()
    rec_card.setObjectName("rec_card")
    rec_card.setStyleSheet(
        f"QFrame#rec_card {{ "
        f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {C['bg_tertiary']}, stop:1 #020A13); "
        f"border: 1px solid {C['border_light']}; border-radius: 8px; }}"
    )
    rec_card.setFixedHeight(132)
    rc_lo = QVBoxLayout(rec_card)
    rc_lo.setContentsMargins(10, 8, 10, 9)
    rc_lo.setSpacing(7)
    rec_header = QWidget()
    rec_header.setFixedHeight(30)
    rrow = QHBoxLayout(rec_header)
    rrow.setContentsMargins(2, 0, 2, 0)
    self.rec_dot = StatusDot()
    self.rec_dot.set_color(C["playing"])
    rrow.addWidget(self.rec_dot)
    self.rec_status = QLabel("IDLE")
    self.rec_status.setStyleSheet(f"color: {C['text']}; font-size: 11px; font-weight: 900; letter-spacing: .7px;")
    rrow.addWidget(self.rec_status)
    rrow.addStretch()
    self.rec_time = QLabel("00:00:00")
    self.rec_time.setStyleSheet(f"color: {C['text']}; font-size: 10px; font-weight: 850;")
    rrow.addWidget(self.rec_time)
    self.rec_actions = QLabel("0")
    self.rec_actions.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; font-weight: 850;")
    rrow.addWidget(self.rec_actions)
    rc_lo.addWidget(rec_header)
    rc_lo.addSpacing(2)
    brow = QHBoxLayout()
    brow.setSpacing(8)
    self.rec_btn = QPushButton("Rec")
    self.rec_btn.setObjectName("rec_round_btn")
    self.rec_btn.setIcon(icon("record", 18, C["error"]))
    self.rec_btn.setIconSize(QSize(18, 18))
    self.rec_btn.setFixedHeight(42)
    self.rec_btn.setStyleSheet(
        f"QPushButton#rec_round_btn {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 9px; font-size: 11px; font-weight: 800; padding: 0 10px; }}"
        f"QPushButton#rec_round_btn:hover {{ border-color: {C['error']}; color: {C['error']}; background-color: {C['bg_hover']}; }}"
        f"QPushButton#rec_round_btn:pressed {{ background-color: {C['bg_pressed']}; }}"
    )
    self.rec_btn.setToolTip("Record (F7)")
    self.rec_btn.clicked.connect(self._toggle_record)
    self.rec_pause_btn = QPushButton("Pause")
    self.rec_pause_btn.setObjectName("rec_pause_btn")
    self.rec_pause_btn.setIcon(icon("pause", 18, C["text"]))
    self.rec_pause_btn.setIconSize(QSize(18, 18))
    self.rec_pause_btn.setFixedHeight(42)
    self.rec_pause_btn.setStyleSheet(
        f"QPushButton#rec_pause_btn {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 9px; font-size: 11px; font-weight: 800; padding: 0 10px; }}"
        f"QPushButton#rec_pause_btn:hover {{ border-color: {C['pause_cyan']}; color: {C['pause_cyan']}; background-color: {C['bg_hover']}; }}"
        f"QPushButton#rec_pause_btn:pressed {{ background-color: {C['bg_pressed']}; }}"
        f"QPushButton#rec_pause_btn:disabled {{ color: {C['text_dark']}; border-color: {C['border']}; }}"
    )
    self.rec_pause_btn.setToolTip("Pause")
    self.rec_pause_btn.setEnabled(False)
    self.rec_pause_btn.clicked.connect(self._toggle_record_pause)
    brow.addWidget(self.rec_btn, 1)
    brow.addWidget(self.rec_pause_btn, 1)
    rc_lo.addLayout(brow)
    sb_lo.addWidget(rec_card)

    self._recorder["btn"] = self.rec_btn
    self._recorder["pause_btn"] = self.rec_pause_btn
    self._recorder["status_dot"] = self.rec_dot
    self._recorder["status_lbl"] = self.rec_status
    self._recorder["time_lbl"] = self.rec_time
    self._recorder["actions_lbl"] = self.rec_actions

    sb_lo.addSpacing(14)

    # ── Playback moved to the main content area in MacroForge 2.0 ──
    # The old sidebar playback card was intentionally removed so the
    # run controls stay visually connected to progress and timeline state.

    # ── Inspector ──
    insp_lbl = QLabel("INSPECTOR  ˅")
    insp_lbl.setObjectName("section")
    insp_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
    sb_lo.addWidget(insp_lbl)
    sb_lo.addSpacing(6)
    insp_card = QFrame()
    insp_card.setObjectName("insp_card")
    insp_card.setStyleSheet(
        f"QFrame#insp_card {{ background-color: {C['bg_card']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; }}"
    )
    icard_lo = QVBoxLayout(insp_card)
    icard_lo.setContentsMargins(8, 8, 8, 8)
    icard_lo.setSpacing(7)

    self.inspector_selector = QComboBox()
    self.inspector_selector.addItem("Select an action")
    self.inspector_selector.setEnabled(False)
    self.inspector_selector.setFixedHeight(36)
    self.inspector_selector.setStyleSheet(
        f"QComboBox {{ background-color: {C['bg_card']}; color: {C['text']}; "
            f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 0 10px; font-size: 11px; }}"
        f"QComboBox:hover {{ border-color: {C['accent']}; }}"
        f"QComboBox:disabled {{ color: {C['text_dark']}; border-color: {C['border']}; }}"
        f"QComboBox::drop-down {{ border: none; }}"
        f"QComboBox::down-arrow {{ width: 10px; height: 10px; }}"
    )
    icard_lo.addWidget(self.inspector_selector)
    icard_lo.addSpacing(8)

    # Toolbar (upgraded styling)
    toolbar_rows = [QHBoxLayout(), QHBoxLayout()]
    for row in toolbar_rows:
        row.setSpacing(5)
        row.setContentsMargins(0, 0, 0, 0)
    for idx, (name, slot, tip, clr) in enumerate([("check", self._apply_inspector, "Apply", C["success"]),
                      ("cross", self._cancel_inspector, "Cancel", C["error"]),
                      ("trash", lambda: self.delete_action(self.active_index), "Delete", C["error"]),
                      ("duplicate", self._duplicate_inspector, "Duplicate", C["accent"]),
                      ("edit", self._open_active_dialog, "Edit", C["accent"])]):
        b = QPushButton()
        b.setObjectName("icon_btn")
        b.setIcon(icon(name, 15, clr))
        b.setToolTip(tip)
        b.setFixedSize(42, 28)
        b.setStyleSheet(
            f"QPushButton {{ padding: 0; background-color: {C['bg_tertiary']}; border: 1px solid {C['border']}; border-radius: 7px; }}"
            f"QPushButton:hover {{ border-color: {clr}; background-color: {C['bg_hover']}; }}"
            f"QPushButton:pressed {{ background-color: {C['bg_pressed']}; }}"
        )
        if slot:
            b.clicked.connect(slot)
        toolbar_rows[idx // 3].addWidget(b)
    for row in toolbar_rows:
        row.addStretch()
        icard_lo.addLayout(row)

    # Empty state
    self.insp_empty = QLabel("Select an action to inspect")
    self.insp_empty.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px; font-style: italic; padding: 6px 0;")
    self.insp_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.insp_empty.setVisible(False)
    icard_lo.addWidget(self.insp_empty)

    # Inspector forms (vertical in sidebar)
    self._insp_lo = QVBoxLayout()
    self._insp_lo.setSpacing(5)
    self._insp_lo.setContentsMargins(0, 0, 0, 0)

    # Key inspector
    self.insp_key = QWidget()
    ik_lo = QVBoxLayout(self.insp_key)
    ik_lo.setContentsMargins(0, 0, 0, 0)
    ik_lo.setSpacing(5)

    def form_label(txt):
        lbl = QLabel(txt)
        lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px; font-weight: 600; background: transparent;")
        return lbl

    def form_input():
        inp = QLineEdit()
        inp.setStyleSheet(
            f"QLineEdit {{ background-color: {C['bg_card']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 6px; padding: 6px 10px; font-size: 10px; }}"
            f"QLineEdit:hover {{ border-color: {C['accent']}; }}"
            f"QLineEdit:focus {{ border-color: {C['accent']}; }}"
        )
        return inp

    self.ik_key = form_input()
    self.ik_key.setPlaceholderText("key")
    self.ik_dur = form_input()
    self.ik_dur.setPlaceholderText("duration")
    self.ik_hold = QCheckBox("Hold mode")
    self.ik_hold.setStyleSheet(f"color: {C['text']}; font-size: 10px; background: transparent;")
    self.ik_repeat = form_input()
    self.ik_repeat.setText("1")
    self.ik_label = form_input()
    self.ik_label.setPlaceholderText("label")
    ik_lo.addWidget(form_label("Key"))
    ik_lo.addWidget(self.ik_key)
    ik_lo.addWidget(form_label("Duration"))
    ik_lo.addWidget(self.ik_dur)
    ik_lo.addWidget(self.ik_hold)
    ik_lo.addWidget(form_label("Repeat"))
    ik_lo.addWidget(self.ik_repeat)
    ik_lo.addWidget(form_label("Label"))
    ik_lo.addWidget(self.ik_label)

    # Pause inspector
    self.insp_pause = QWidget()
    ip_lo = QVBoxLayout(self.insp_pause)
    ip_lo.setContentsMargins(0, 0, 0, 0)
    ip_lo.setSpacing(5)
    self.ip_dur = form_input()
    self.ip_dur.setPlaceholderText("duration")
    self.ip_label = form_input()
    self.ip_label.setPlaceholderText("label")
    ip_lo.addWidget(form_label("Duration"))
    ip_lo.addWidget(self.ip_dur)
    ip_lo.addWidget(form_label("Label"))
    ip_lo.addWidget(self.ip_label)

    # Click inspector
    self.insp_click = QWidget()
    ic_lo = QVBoxLayout(self.insp_click)
    ic_lo.setContentsMargins(0, 0, 0, 0)
    ic_lo.setSpacing(5)
    self.ic_x = form_input()
    self.ic_x.setPlaceholderText("x")
    self.ic_y = form_input()
    self.ic_y.setPlaceholderText("y")
    self.ic_btn = QComboBox()
    self.ic_btn.addItems(["left", "right", "middle"])
    self.ic_btn.setStyleSheet(
        f"QComboBox {{ background-color: {C['bg_card']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 6px; padding: 6px 10px; font-size: 10px; }}"
        f"QComboBox:hover {{ border-color: {C['accent']}; }}"
        f"QComboBox::drop-down {{ border: none; }}"
    )
    self.ic_rand = form_input()
    self.ic_rand.setPlaceholderText("rand")
    self.ic_repeat = form_input()
    self.ic_repeat.setText("1")
    self.ic_label = form_input()
    self.ic_label.setPlaceholderText("label")
    ic_lo.addWidget(form_label("X, Y"))
    xy_row = QHBoxLayout()
    xy_row.setSpacing(5)
    xy_row.addWidget(self.ic_x)
    xy_row.addWidget(self.ic_y)
    ic_lo.addLayout(xy_row)
    ic_lo.addWidget(form_label("Button"))
    ic_lo.addWidget(self.ic_btn)
    ic_lo.addWidget(form_label("Randomness"))
    ic_lo.addWidget(self.ic_rand)
    ic_lo.addWidget(form_label("Repeat"))
    ic_lo.addWidget(self.ic_repeat)
    ic_lo.addWidget(form_label("Label"))
    ic_lo.addWidget(self.ic_label)

    # Image inspector
    self.insp_image = QWidget()
    ii_lo = QVBoxLayout(self.insp_image)
    ii_lo.setContentsMargins(0, 0, 0, 0)
    ii_lo.setSpacing(5)
    self.ii_sim = form_input()
    self.ii_sim.setText("0.8")
    self.ii_wait = form_input()
    self.ii_wait.setText("10.0")
    ii_lo.addWidget(form_label("Similarity"))
    ii_lo.addWidget(self.ii_sim)
    ii_lo.addWidget(form_label("Wait timeout"))
    ii_lo.addWidget(self.ii_wait)

    # Group inspector
    self.insp_group = QWidget()
    ig_lo = QVBoxLayout(self.insp_group)
    ig_lo.setContentsMargins(0, 0, 0, 0)
    ig_lo.setSpacing(5)
    self.ig_name = form_input()
    self.ig_name.setPlaceholderText("group name")
    self.ig_collapsed = QCheckBox("Collapsed")
    self.ig_collapsed.setStyleSheet(f"color: {C['text']}; font-size: 10px; background: transparent;")
    self.ig_meta = QLabel("0 actions · ~0.0s")
    self.ig_meta.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
    ig_lo.addWidget(form_label("Group name"))
    ig_lo.addWidget(self.ig_name)
    ig_lo.addWidget(self.ig_collapsed)
    ig_lo.addWidget(self.ig_meta)

    # Loop inspector
    self.insp_loop = QWidget()
    il_lo = QVBoxLayout(self.insp_loop)
    il_lo.setContentsMargins(0, 0, 0, 0)
    il_lo.setSpacing(5)
    self.il_label = form_input()
    self.il_label.setPlaceholderText("loop label")
    self.il_count = QSpinBox()
    self.il_count.setRange(2, 9999)
    self.il_count.setStyleSheet(f"QSpinBox {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; font-size: 10px; }}")
    self.il_target = QComboBox()
    self.il_target.setStyleSheet(f"QComboBox {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; font-size: 10px; }} QComboBox::drop-down {{ border: none; }}")
    il_lo.addWidget(form_label("Label"))
    il_lo.addWidget(self.il_label)
    il_lo.addWidget(form_label("Repeat count"))
    il_lo.addWidget(self.il_count)
    il_lo.addWidget(form_label("Target"))
    il_lo.addWidget(self.il_target)

    # Condition inspector
    self.insp_condition = QWidget()
    ico_lo = QVBoxLayout(self.insp_condition)
    ico_lo.setContentsMargins(0, 0, 0, 0)
    ico_lo.setSpacing(5)
    self.ico_label = form_input()
    self.ico_label.setPlaceholderText("condition label")
    self.ico_type = QComboBox()
    self.ico_type.addItems(["pixel_color", "variable", "none"])
    self.ico_type.setStyleSheet(f"QComboBox {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; font-size: 10px; }} QComboBox::drop-down {{ border: none; }}")
    self.ico_true = QComboBox()
    self.ico_false = QComboBox()
    for combo in (self.ico_true, self.ico_false):
        combo.setStyleSheet(f"QComboBox {{ background-color: {C['bg_card']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 5px 8px; font-size: 10px; }} QComboBox::drop-down {{ border: none; }}")
    self.ico_rule = QLabel("Edit for pixel/variable values")
    self.ico_rule.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
    ico_lo.addWidget(form_label("Label"))
    ico_lo.addWidget(self.ico_label)
    ico_lo.addWidget(form_label("Type"))
    ico_lo.addWidget(self.ico_type)
    ico_lo.addWidget(form_label("True target"))
    ico_lo.addWidget(self.ico_true)
    ico_lo.addWidget(form_label("False target"))
    ico_lo.addWidget(self.ico_false)
    ico_lo.addWidget(self.ico_rule)

    self._insp_lo.addWidget(self.insp_key)
    self._insp_lo.addWidget(self.insp_pause)
    self._insp_lo.addWidget(self.insp_click)
    self._insp_lo.addWidget(self.insp_image)
    self._insp_lo.addWidget(self.insp_group)
    self._insp_lo.addWidget(self.insp_loop)
    self._insp_lo.addWidget(self.insp_condition)
    for w in (self.insp_key, self.insp_pause, self.insp_click, self.insp_image, self.insp_group, self.insp_loop, self.insp_condition):
        w.setVisible(False)
    icard_lo.addLayout(self._insp_lo)
    sb_lo.addWidget(insp_card)
    sb_lo.addStretch()

    main_lo.addWidget(sidebar)

    # ━━ Content area ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    content = QFrame()
    content_lo = QVBoxLayout(content)
    content_lo.setContentsMargins(0, 0, 0, 0)
    content_lo.setSpacing(0)

    # ── Streamlined command/header dock ──
    header_shell = QFrame()
    header_shell.setFixedHeight(62)
    header_shell.setStyleSheet(f"background-color: {C['bg']}; border: none;")
    shell_lo = QVBoxLayout(header_shell)
    shell_lo.setContentsMargins(8, 6, 8, 0)
    shell_lo.setSpacing(0)

    header_dock = QFrame()
    header_dock.setObjectName("header_dock")
    header_dock.setStyleSheet(
        f"QFrame#header_dock {{ background-color: {C['bg_card']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 12px; }}"
    )
    dock_lo = QHBoxLayout(header_dock)
    dock_lo.setContentsMargins(10, 7, 10, 7)
    dock_lo.setSpacing(8)

    # Left command cluster. The old TIMELINE title/subtitle was removed so the
    # header is one clean control surface instead of stacked panels.
    left_cluster = QFrame()
    left_cluster.setStyleSheet("background: transparent; border: none;")
    left_lo = QHBoxLayout(left_cluster)
    left_lo.setContentsMargins(0, 0, 0, 0)
    left_lo.setSpacing(6)

    def header_icon_button(obj, icon_name, color, tooltip, slot):
        btn = QPushButton()
        btn.setObjectName(obj)
        btn.setIcon(icon(icon_name, 16, color))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(tooltip)
        btn.setFixedSize(34, 34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton#{obj} {{ background-color: {C['bg_tertiary']}; color: {color}; "
            f"border: 1px solid {C['border']}; border-radius: 9px; padding: 0; }}"
            f"QPushButton#{obj}:hover {{ border-color: {color}; background-color: {C['bg_hover']}; }}"
            f"QPushButton#{obj}:pressed {{ background-color: {C['bg_pressed']}; }}"
        )
        btn.clicked.connect(slot)
        return btn

    self.editor_mode_btn = header_icon_button("editor_mode_btn", "edit", C["accent"], "Open macro editor mode", self.open_macro_editor)
    left_lo.addWidget(self.editor_mode_btn)

    self.preflight_btn = header_icon_button("preflight_btn", "check", C["success"], "Run macro health / pre-flight checker", self.open_preflight_report)
    left_lo.addWidget(self.preflight_btn)

    self.runtime_log_btn = header_icon_button("runtime_log_btn", "eye", C["pause_cyan"], "Show / hide live runtime log", self.toggle_runtime_log_panel)
    self.runtime_log_btn.setCheckable(True)
    left_lo.addWidget(self.runtime_log_btn)

    self.compact_view_btn = header_icon_button("view_toggle", "menu", C["accent"], "Timeline list view", lambda: None)
    self.compact_view_btn.setCheckable(True)
    self.compact_view_btn.setChecked(True)
    left_lo.addWidget(self.compact_view_btn)

    self.tl_search = QLineEdit()
    self.tl_search.setPlaceholderText("Search actions…")
    self.tl_search.setClearButtonEnabled(True)
    self.tl_search.setMinimumWidth(84)
    self.tl_search.setMaximumWidth(150)
    self.tl_search.setFixedHeight(34)
    self.tl_search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.tl_search.addAction(icon("search", 16, C["text_dim"]), QLineEdit.ActionPosition.LeadingPosition)
    self.tl_search.setStyleSheet(
        f"QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 9px; padding: 4px 10px; font-size: 12px; }} "
        f"QLineEdit:focus {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
    )
    self.tl_search.textChanged.connect(lambda t: self.timeline.set_search(t))
    left_lo.addWidget(self.tl_search, stretch=1)
    dock_lo.addWidget(left_cluster, stretch=1)

    # Hidden compatibility label for code/tests that update macro_summary. It is
    # no longer displayed under a TIMELINE heading.
    self.macro_summary = QLabel("0 actions · 0 image checks · ~0s")
    self.macro_summary.setVisible(False)

    # Center status capsule: auto-resizes up to a cap as status text changes.
    status_pill = QFrame()
    status_pill.setObjectName("status_pill")
    status_pill.setMinimumWidth(180)
    status_pill.setMaximumWidth(360)
    status_pill.setFixedHeight(40)
    status_pill.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    status_pill.setStyleSheet(
        f"QFrame#status_pill {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 10px; }}"
    )
    self.status_pill = status_pill
    sp_lo = QHBoxLayout(status_pill)
    sp_lo.setContentsMargins(12, 0, 12, 0)
    sp_lo.setSpacing(8)
    self.status_dot = StatusDot()
    self.status_dot.set_color(C["playing"])
    self.status_dot.setFixedSize(16, 16)
    sp_lo.addWidget(self.status_dot)

    self.status_icon = QLabel()
    self.status_icon.setPixmap(icon("check", 16, C["success"]).pixmap(16, 16))
    self.status_icon.setFixedSize(18, 18)
    self.status_icon.setScaledContents(True)
    self.status_icon.setVisible(False)
    sp_lo.addWidget(self.status_icon)

    self.status_text = QLabel("Ready")
    self.status_text.setStyleSheet(f"color: {C['text']}; font-size: 13px; background: transparent;")
    self.status_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.status_text.setWordWrap(False)
    sp_lo.addWidget(self.status_text, stretch=1)
    dock_lo.addWidget(status_pill, stretch=0)

    # Right cluster: profile selector stays with check-update and menu buttons.
    right_cluster = QFrame()
    right_cluster.setStyleSheet("background: transparent; border: none;")
    right_lo = QHBoxLayout(right_cluster)
    right_lo.setContentsMargins(0, 0, 0, 0)
    right_lo.setSpacing(6)

    self.profile_btn = QPushButton("Default")
    self.profile_btn.setObjectName("profile_switcher")
    self.profile_btn.setIcon(icon("folder", 16, C["accent"]))
    self.profile_btn.setIconSize(QSize(15, 15))
    self.profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.profile_btn.setToolTip("Switch profile")
    self.profile_btn.setStyleSheet(
        f"QPushButton#profile_switcher {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 9px; padding: 6px 10px; "
        f"font-size: 12px; text-align: left; }} "
        f"QPushButton#profile_switcher:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
    )
    self.profile_btn.setFixedSize(112, 34)
    self.profile_btn.clicked.connect(self._show_profile_menu)
    right_lo.addWidget(self.profile_btn)

    up_btn = header_icon_button("update_top_btn", "update", C["accent"], "Check for updates", self._check_update_manual)
    up_btn.setIconSize(QSize(17, 17))
    self.update_top_btn = up_btn
    right_lo.addWidget(up_btn)

    gear = header_icon_button("menu_top_btn", "menu", C["text_dim"], "Menu", self._show_action_menu)
    gear.setIconSize(QSize(17, 17))
    self.menu_top_btn = gear
    right_lo.addWidget(gear)
    dock_lo.addWidget(right_cluster, stretch=0)

    shell_lo.addWidget(header_dock)
    content_lo.addWidget(header_shell)

    self.timeline = TimelineView(model=self.action_model)
    content_lo.addWidget(self.timeline, stretch=1)

    # Live runtime log panel. Hidden by default; opened from the top eye button
    # or playback diagnostics menu. It mirrors the diagnostic stream without
    # stealing vertical space during normal editing.
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
    rlp_head.setContentsMargins(0, 0, 0, 0)
    rlp_title = QLabel("LIVE RUNTIME LOG")
    rlp_title.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; letter-spacing: 1px; background: transparent;")
    rlp_head.addWidget(rlp_title)
    rlp_head.addStretch()
    clear_log_btn = QPushButton("Clear")
    clear_log_btn.setFixedSize(54, 24)
    clear_log_btn.setStyleSheet(
        f"QPushButton {{ color: {C['text_dim']}; background-color: {C['bg_tertiary']}; border: 1px solid {C['border']}; border-radius: 7px; font-size: 10px; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
    )
    clear_log_btn.clicked.connect(self.clear_runtime_log_panel)
    rlp_head.addWidget(clear_log_btn)
    hide_log_btn = QPushButton("Hide")
    hide_log_btn.setFixedSize(50, 24)
    hide_log_btn.setStyleSheet(clear_log_btn.styleSheet())
    hide_log_btn.clicked.connect(lambda: self.toggle_runtime_log_panel(False))
    rlp_head.addWidget(hide_log_btn)
    rlp_lo.addLayout(rlp_head)
    self.runtime_log_edit = QPlainTextEdit()
    self.runtime_log_edit.setReadOnly(True)
    self.runtime_log_edit.setMaximumBlockCount(600)
    self.runtime_log_edit.setStyleSheet(
        f"QPlainTextEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; padding: 6px; font-family: Consolas, monospace; font-size: 10px; }}"
    )
    rlp_lo.addWidget(self.runtime_log_edit, stretch=1)
    content_lo.addWidget(self.runtime_log_panel)

    self.playback_panel = self._make_playback_panel()
    content_lo.addWidget(self.playback_panel)

    main_lo.addWidget(content, stretch=1)
