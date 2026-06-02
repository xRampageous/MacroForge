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
    QPushButton,
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

    sb_lo.addSpacing(14)

    # ── Recorder ──
    rec_lbl = QLabel("RECORDER  ˅")
    rec_lbl.setObjectName("section")
    rec_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
    sb_lo.addWidget(rec_lbl)
    sb_lo.addSpacing(6)
    rec_card = QFrame()
    rec_card.setObjectName("rec_card")
    rec_card.setStyleSheet(
        f"QFrame#rec_card {{ background-color: {C['bg_card']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; }}"
    )
    rec_card.setFixedHeight(120)
    rc_lo = QVBoxLayout(rec_card)
    rc_lo.setContentsMargins(8, 7, 8, 7)
    rc_lo.setSpacing(5)
    rec_header = QWidget()
    rec_header.setFixedHeight(30)
    rrow = QHBoxLayout(rec_header)
    rrow.setContentsMargins(2, 0, 2, 0)
    self.rec_dot = StatusDot()
    self.rec_dot.set_color(C["playing"])
    rrow.addWidget(self.rec_dot)
    self.rec_status = QLabel("IDLE")
    self.rec_status.setStyleSheet(f"color: {C['text']}; font-size: 10px; font-weight: 800; letter-spacing: .6px;")
    rrow.addWidget(self.rec_status)
    rrow.addStretch()
    self.rec_time = QLabel("00:00:00")
    self.rec_time.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; font-weight: 700;")
    rrow.addWidget(self.rec_time)
    self.rec_actions = QLabel("0")
    self.rec_actions.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; font-weight: 700;")
    rrow.addWidget(self.rec_actions)
    rc_lo.addWidget(rec_header)
    rc_lo.addSpacing(2)
    brow = QHBoxLayout()
    brow.setSpacing(8)
    self.rec_btn = QPushButton("Rec")
    self.rec_btn.setObjectName("rec_round_btn")
    self.rec_btn.setIcon(icon("record", 18, C["error"]))
    self.rec_btn.setIconSize(QSize(18, 18))
    self.rec_btn.setFixedHeight(40)
    self.rec_btn.setStyleSheet(
        f"QPushButton#rec_round_btn {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; font-size: 11px; font-weight: 600; padding: 0 12px; }}"
        f"QPushButton#rec_round_btn:hover {{ border-color: {C['error']}; color: {C['error']}; background-color: {C['bg_hover']}; }}"
        f"QPushButton#rec_round_btn:pressed {{ background-color: {C['bg_pressed']}; }}"
    )
    self.rec_btn.setToolTip("Record (F7)")
    self.rec_btn.clicked.connect(self._toggle_record)
    self.rec_pause_btn = QPushButton("Pause")
    self.rec_pause_btn.setObjectName("rec_pause_btn")
    self.rec_pause_btn.setIcon(icon("pause", 18, C["text"]))
    self.rec_pause_btn.setIconSize(QSize(18, 18))
    self.rec_pause_btn.setFixedHeight(40)
    self.rec_pause_btn.setStyleSheet(
        f"QPushButton#rec_pause_btn {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; font-size: 11px; font-weight: 600; padding: 0 12px; }}"
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
    insp_card.setStyleSheet("QFrame#insp_card { background: transparent; border: none; }")
    icard_lo = QVBoxLayout(insp_card)
    icard_lo.setContentsMargins(0, 0, 0, 0)
    icard_lo.setSpacing(8)

    self.inspector_selector = QComboBox()
    self.inspector_selector.addItem("Select an action")
    self.inspector_selector.setEnabled(False)
    self.inspector_selector.setFixedHeight(40)
    self.inspector_selector.setStyleSheet(
        f"QComboBox {{ background-color: {C['bg_card']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; padding: 0 12px; font-size: 11px; }}"
        f"QComboBox:hover {{ border-color: {C['accent']}; }}"
        f"QComboBox:disabled {{ color: {C['text_dark']}; border-color: {C['border']}; }}"
        f"QComboBox::drop-down {{ border: none; }}"
        f"QComboBox::down-arrow {{ width: 10px; height: 10px; }}"
    )
    icard_lo.addWidget(self.inspector_selector)
    icard_lo.addSpacing(8)

    # Toolbar (upgraded styling)
    ibrow = QHBoxLayout()
    ibrow.setSpacing(6)
    for name, slot, tip, clr in [("check", self._apply_inspector, "Apply", C["success"]),
                      ("play", self.test_selected_action, "Test selected action", C["success"]),
                      ("cross", self._cancel_inspector, "Cancel", C["error"]),
                      ("trash", lambda: self.delete_action(self.active_index), "Delete", C["error"]),
                      ("duplicate", self._duplicate_inspector, "Duplicate", C["accent"]),
                      ("edit", self._open_active_dialog, "Edit", C["accent"])]:
        b = QPushButton()
        b.setObjectName("icon_btn")
        b.setIcon(icon(name, 16, clr))
        b.setToolTip(tip)
        b.setFixedSize(32, 32)
        b.setStyleSheet(
            f"QPushButton {{ padding: 0; background-color: {C['bg_card']}; border: 1px solid {C['border']}; border-radius: 8px; }}"
            f"QPushButton:hover {{ border-color: {clr}; background-color: {C['bg_hover']}; }}"
            f"QPushButton:pressed {{ background-color: {C['bg_pressed']}; }}"
        )
        if slot:
            b.clicked.connect(slot)
        ibrow.addWidget(b)
    ibrow.addStretch()
    icard_lo.addLayout(ibrow)

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

    self._insp_lo.addWidget(self.insp_key)
    self._insp_lo.addWidget(self.insp_pause)
    self._insp_lo.addWidget(self.insp_click)
    self._insp_lo.addWidget(self.insp_image)
    for w in (self.insp_key, self.insp_pause, self.insp_click, self.insp_image):
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

    # ── Unified header dock ──
    header_shell = QFrame()
    header_shell.setFixedHeight(84)
    header_shell.setStyleSheet(f"background-color: {C['bg']}; border: none;")
    shell_lo = QVBoxLayout(header_shell)
    shell_lo.setContentsMargins(8, 6, 8, 0)
    shell_lo.setSpacing(0)

    header_dock = QFrame()
    header_dock.setObjectName("header_dock")
    header_dock.setStyleSheet(
        f"QFrame#header_dock {{ background-color: {C['bg_card']}; "
        f"border: 1px solid {C['border']}; border-radius: 12px; }}"
    )
    dock_lo = QVBoxLayout(header_dock)
    dock_lo.setContentsMargins(10, 5, 10, 4)
    dock_lo.setSpacing(2)

    title = QFrame()
    title.setObjectName("topbar")
    title.setStyleSheet("QFrame#topbar { background: transparent; border: none; }")
    tl = QHBoxLayout(title)
    tl.setContentsMargins(0, 0, 0, 0)
    tl.setSpacing(0)

    # Profile switcher (left)
    self.profile_btn = QPushButton("Default")
    self.profile_btn.setObjectName("profile_switcher")
    self.profile_btn.setIcon(icon("folder", 18, C["accent"]))
    self.profile_btn.setIconSize(QSize(16, 16))
    self.profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.profile_btn.setToolTip("Switch profile")
    self.profile_btn.setStyleSheet(
        f"QPushButton#profile_switcher {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 7px 12px; "
        f"font-size: 13px; font-weight: 500; text-align: left; }} "
        f"QPushButton#profile_switcher:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
    )
    self.profile_btn.setFixedSize(108, 34)
    self.profile_btn.clicked.connect(self._show_profile_menu)
    tl.addWidget(self.profile_btn)
    tl.addSpacing(8)

    # Check update button (upgraded, moved to left)
    up_btn = QPushButton()
    up_btn.setObjectName("update_top_btn")
    up_btn.setIcon(icon("update", 18, C["accent"]))
    up_btn.setIconSize(QSize(18, 18))
    up_btn.setToolTip("Check for updates")
    up_btn.setFixedSize(40, 40)
    up_btn.setStyleSheet(
        f"QPushButton#update_top_btn {{ background-color: {C['bg_card']}; color: {C['accent']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; padding: 0; }}"
        f"QPushButton#update_top_btn:hover {{ border-color: {C['accent']}; background-color: {C['bg_tertiary']}; "
        f"transform: scale(1.05); }}"
        f"QPushButton#update_top_btn:pressed {{ background-color: {C['bg_hover']}; }}"
    )
    up_btn.clicked.connect(self._check_update_manual)
    tl.addWidget(up_btn)
    tl.addSpacing(8)

    # Menu button (upgraded, moved to left)
    gear = QPushButton()
    gear.setObjectName("menu_top_btn")
    gear.setIcon(icon("menu", 18, C["text_dim"]))
    gear.setIconSize(QSize(18, 18))
    gear.setToolTip("Menu")
    gear.setFixedSize(40, 40)
    gear.setStyleSheet(
        f"QPushButton#menu_top_btn {{ background-color: {C['bg_card']}; color: {C['text_dim']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; padding: 0; }}"
        f"QPushButton#menu_top_btn:hover {{ border-color: {C['accent']}; color: {C['accent']}; "
        f"background-color: {C['bg_tertiary']}; transform: scale(1.05); }}"
        f"QPushButton#menu_top_btn:pressed {{ background-color: {C['bg_hover']}; }}"
    )
    gear.clicked.connect(self._show_action_menu)
    tl.addWidget(gear)

    tl.addStretch()

    # Status indicator - centered, wider, larger font, with icon indicators
    status_pill = QFrame()
    status_pill.setObjectName("status_pill")
    status_pill.setStyleSheet(
        f"QFrame#status_pill {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; }}"
    )
    status_pill.setFixedSize(220, 44)
    sp_lo = QHBoxLayout(status_pill)
    sp_lo.setContentsMargins(14, 0, 14, 0)
    sp_lo.setSpacing(10)
    self.status_dot = StatusDot()
    self.status_dot.set_color(C["playing"])
    self.status_dot.setFixedSize(16, 16)
    sp_lo.addWidget(self.status_dot)

    # Status icon for different states
    self.status_icon = QLabel()
    self.status_icon.setPixmap(icon("check", 16, C["success"]).pixmap(16, 16))
    self.status_icon.setFixedSize(20, 20)
    self.status_icon.setScaledContents(True)
    self.status_icon.setVisible(False)
    sp_lo.addWidget(self.status_icon)

    self.status_text = QLabel("Ready")
    self.status_text.setStyleSheet(f"color: {C['text']}; font-size: 12px; font-weight: 600; background: transparent;")
    sp_lo.addWidget(self.status_text)
    tl.addWidget(status_pill)

    tl.addStretch()
    dock_lo.addWidget(title)

    dock_lo.addWidget(self._hsep())

    # Timeline command strip
    tl_header = QFrame()
    tl_header.setObjectName("timeline_header")
    tl_header.setStyleSheet("QFrame#timeline_header { background: transparent; border: none; }")
    tl_hl = QHBoxLayout(tl_header)
    tl_hl.setContentsMargins(0, 0, 0, 0)
    tl_hl.setSpacing(10)

    header_stack = QVBoxLayout()
    header_stack.setContentsMargins(0, 0, 0, 0)
    header_stack.setSpacing(0)
    tl_lbl = QLabel("TIMELINE")
    tl_lbl.setStyleSheet(f"color: {C['text']}; font-size: 15px; font-weight: 600;")
    header_stack.addWidget(tl_lbl)
    hints = QLabel("Drag rows to reorder")
    hints.setStyleSheet(f"color: {C['text_dark']}; font-size: 9px;")
    hints.setVisible(False)
    header_stack.addWidget(hints)
    self.macro_summary = QLabel("0 actions · 0 image checks · ~0s")
    self.macro_summary.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px; font-weight: 600;")
    header_stack.addWidget(self.macro_summary)
    tl_hl.addLayout(header_stack)
    tl_hl.addStretch()

    self.compact_view_btn = QPushButton()
    self.compact_view_btn.setObjectName("view_toggle")
    self.compact_view_btn.setIcon(icon("menu", 17, C["accent"]))
    self.compact_view_btn.setToolTip("Timeline list view")
    self.compact_view_btn.setCheckable(True)
    self.compact_view_btn.setChecked(True)
    self.compact_view_btn.setFixedSize(34, 26)
    tl_hl.addWidget(self.compact_view_btn)

    self.tl_search = QLineEdit()
    self.tl_search.setPlaceholderText("Search actions…")
    self.tl_search.setClearButtonEnabled(True)
    self.tl_search.setFixedWidth(170)
    self.tl_search.setFixedHeight(26)
    self.tl_search.addAction(icon("search", 16, C["text_dim"]), QLineEdit.ActionPosition.LeadingPosition)
    self.tl_search.setStyleSheet(
        f"QLineEdit {{ background-color: {C['bg_card']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 10px; font-size: 11px; }} "
        f"QLineEdit:focus {{ border-color: {C['accent']}; background-color: {C['bg_tertiary']}; }}"
    )
    self.tl_search.textChanged.connect(lambda t: self.timeline.set_search(t))
    tl_hl.addWidget(self.tl_search)
    dock_lo.addWidget(tl_header)
    shell_lo.addWidget(header_dock)
    content_lo.addWidget(header_shell)

    self.timeline = TimelineView(model=self.action_model)
    content_lo.addWidget(self.timeline, stretch=1)

    self.playback_panel = self._make_playback_panel()
    content_lo.addWidget(self.playback_panel)

    main_lo.addWidget(content, stretch=1)
