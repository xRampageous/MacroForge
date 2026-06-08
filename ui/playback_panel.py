"""Playback panel construction for MacroForge main window."""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from ui.icons import icon
from ui.theme import COLORS


def make_playback_panel(window):
    self = window
    C = COLORS

    panel = QFrame()
    panel.setObjectName("mf3_playback_panel")
    panel.setFixedHeight(184)
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    panel.setStyleSheet(f"QFrame#mf3_playback_panel {{ background-color: {C['bg']}; border: none; }}")

    lo = QVBoxLayout(panel)
    lo.setContentsMargins(8, 3, 8, 6)
    lo.setSpacing(0)

    dock = QFrame()
    dock.setObjectName("mf3_playback_dock")
    dock.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    dock.setStyleSheet(
        f"QFrame#mf3_playback_dock {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 {C['bg_secondary']}, stop:0.55 {C['bg_card']}, stop:1 #010915); "
        f"border: 1px solid {C['border']}; border-radius: 10px; }}"
        "QFrame#mf3_playback_dock QLabel { background: transparent; border: none; }"
    )
    dlo = QVBoxLayout(dock)
    dlo.setContentsMargins(11, 7, 11, 7)
    dlo.setSpacing(5)

    def section_title(text, icon_name, color):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        ico = QLabel()
        ico.setPixmap(icon(icon_name, 18, color).pixmap(18, 18))
        ico.setFixedSize(20, 20)
        row.addWidget(ico)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 13px; font-weight: 900; "
            "letter-spacing: 0; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch()
        return row

    def tiny_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; font-weight: 850; background: transparent;"
        )
        return lbl

    def vertical_rule():
        rule = QFrame()
        rule.setObjectName("playback_vertical_rule")
        rule.setFixedWidth(1)
        rule.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        rule.setStyleSheet(f"QFrame#playback_vertical_rule {{ background-color: {C['border']}; border: none; }}")
        return rule

    def chip_style(name, color=None):
        active = color or C["accent"]
        return (
            f"QFrame#{name} {{ background-color: {C['bg_tertiary']}; border: 1px solid {C['border']}; "
            "border-radius: 8px; }}"
            f"QFrame#{name}:hover {{ border-color: {C['border_light']}; }}"
            f"QFrame#{name}[checked=\"true\"] {{ border-color: {active}; background-color: {C['accent_glow']}; }}"
        )

    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(12)

    play_section = QFrame()
    play_section.setObjectName("playback_block")
    play_section.setFixedWidth(266)
    play_section.setStyleSheet("QFrame#playback_block { background: transparent; border: none; }")
    play_lo = QVBoxLayout(play_section)
    play_lo.setContentsMargins(0, 0, 0, 0)
    play_lo.setSpacing(5)
    play_lo.addLayout(section_title("PLAYBACK", "play", C["accent"]))

    play_row = QHBoxLayout()
    play_row.setContentsMargins(0, 0, 0, 0)
    play_row.setSpacing(4)
    self.start_btn = QPushButton()
    self.start_btn.setObjectName("play_btn")
    self.start_btn.setIcon(icon("play", 18, C["success"]))
    self.start_btn.setIconSize(QSize(18, 18))
    self.start_btn.setToolTip("Start playback (F9)")
    self.start_btn.setFixedSize(54, 40)
    self.start_btn.clicked.connect(self.start)
    play_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton()
    self.pause_btn.setObjectName("pause_btn")
    self.pause_btn.setIcon(icon("pause", 17, C["pause_cyan"]))
    self.pause_btn.setIconSize(QSize(17, 17))
    self.pause_btn.setToolTip("Pause / resume playback (Esc)")
    self.pause_btn.setFixedSize(54, 40)
    self.pause_btn.setEnabled(False)
    self.pause_btn.clicked.connect(self.engine.toggle_pause)
    play_row.addWidget(self.pause_btn)

    self.stop_btn = QPushButton()
    self.stop_btn.setObjectName("stop_btn")
    self.stop_btn.setIcon(icon("stop", 16, C["error"]))
    self.stop_btn.setIconSize(QSize(16, 16))
    self.stop_btn.setToolTip("Stop playback")
    self.stop_btn.setFixedSize(54, 40)
    self.stop_btn.setEnabled(False)
    self.stop_btn.clicked.connect(self.stop)
    play_row.addWidget(self.stop_btn)

    self.preflight_btn = QPushButton()
    self.preflight_btn.setObjectName("preflight_btn")
    self.preflight_btn.setIcon(icon("check", 16, C["accent"]))
    self.preflight_btn.setIconSize(QSize(16, 16))
    self.preflight_btn.setToolTip("Macro health / pre-flight check (Ctrl+Shift+P)")
    self.preflight_btn.setFixedSize(54, 40)
    self.preflight_btn.clicked.connect(self.open_preflight_report)
    play_row.addWidget(self.preflight_btn)
    play_row.addStretch()
    play_lo.addLayout(play_row)

    feedback_frame = QFrame()
    feedback_frame.setObjectName("playback_feedback_frame")
    feedback_frame.setFixedSize(262, 28)
    feedback_frame.setProperty("feedback_state", "ready")
    feedback_frame.setToolTip("Playback status")
    feedback_frame.setStyleSheet(
        f"QFrame#playback_feedback_frame {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {C['accent_glow']}, stop:1 {C['bg_tertiary']}); "
        f"border: 1px solid {C['accent_dim']}; border-radius: 8px; }}"
    )
    feedback_lo = QHBoxLayout(feedback_frame)
    feedback_lo.setContentsMargins(6, 0, 8, 0)
    feedback_lo.setSpacing(6)
    self.playback_feedback_icon = QLabel()
    self.playback_feedback_icon.setObjectName("playback_feedback_icon")
    self.playback_feedback_icon.setFixedSize(21, 19)
    self.playback_feedback_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.playback_feedback_icon.setPixmap(icon("bolt", 15, C["accent"]).pixmap(15, 15))
    self.playback_feedback_icon.setStyleSheet(
        f"QLabel#playback_feedback_icon {{ background-color: {C['bg_secondary']}; "
        f"border: 1px solid {C['accent_dim']}; border-radius: 6px; }}"
    )
    feedback_lo.addWidget(self.playback_feedback_icon)

    self.playback_feedback_label = QLabel("Playback ready")
    self.playback_feedback_label.setObjectName("playback_feedback")
    self.playback_feedback_label.setFixedHeight(22)
    self.playback_feedback_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.playback_feedback_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.playback_feedback_label.setToolTip("Playback status")
    self.playback_feedback_label.setStyleSheet(
        f"QLabel#playback_feedback {{ color: {C['accent']}; "
        "font-size: 11px; font-weight: 900; background: transparent; border: none; }}"
    )
    feedback_lo.addWidget(self.playback_feedback_label, stretch=1)
    self.playback_feedback_frame = feedback_frame
    play_lo.addWidget(feedback_frame, alignment=Qt.AlignmentFlag.AlignLeft)
    top.addWidget(play_section)
    top.addWidget(vertical_rule())

    options_section = QFrame()
    options_section.setObjectName("options_block")
    options_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    options_section.setStyleSheet("QFrame#options_block { background: transparent; border: none; }")
    opt_lo = QVBoxLayout(options_section)
    opt_lo.setContentsMargins(0, 0, 0, 0)
    opt_lo.setSpacing(4)
    opt_lo.addLayout(section_title("OPTIONS", "settings", C["text_dim"]))

    options_body = QHBoxLayout()
    options_body.setContentsMargins(0, 0, 0, 0)
    options_body.setSpacing(12)

    speed_box = QVBoxLayout()
    speed_box.setContentsMargins(0, 0, 0, 0)
    speed_box.setSpacing(4)
    speed_box.addWidget(tiny_label("Speed"))
    self.speed_combo = QComboBox()
    self.speed_combo.addItems(["0.1x", "0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "3.0x", "4.0x"])
    self.speed_combo.setCurrentText("1.0x")
    self.speed_combo.currentTextChanged.connect(self._on_speed_change)
    self.speed_combo.setFixedHeight(30)
    self.speed_combo.setFixedWidth(58)
    self.speed_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    self.speed_combo.setStyleSheet(
        f"QComboBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 4px 6px; "
        "font-size: 12px; font-weight: 800; }}"
        f"QComboBox:hover {{ border-color: {C['accent_dim']}; }}"
        "QComboBox::drop-down { border: none; width: 0px; }"
        "QComboBox::down-arrow { image: none; width: 0px; height: 0px; }"
    )
    self.speed_slider = QSlider(Qt.Orientation.Horizontal)
    self.speed_slider.setObjectName("playback_speed_slider")
    self.speed_slider.setRange(0, self.speed_combo.count() - 1)
    self.speed_slider.setValue(self.speed_combo.currentIndex())
    self.speed_slider.setTickInterval(1)
    self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    self.speed_slider.setFixedHeight(22)
    self.speed_slider.setMinimumWidth(128)
    self.speed_slider.setStyleSheet(
        f"QSlider#playback_speed_slider::groove:horizontal {{ height: 7px; background: {C['lane']}; border-radius: 4px; }}"
        f"QSlider#playback_speed_slider::sub-page:horizontal {{ background: {C['accent']}; border-radius: 4px; }}"
        f"QSlider#playback_speed_slider::handle:horizontal {{ background: {C['accent']}; width: 17px; height: 17px; "
        f"border-radius: 9px; margin: -5px 0; }}"
        f"QSlider#playback_speed_slider::handle:horizontal:hover {{ background: {C['accent_hover']}; }}"
    )
    self.speed_slider.valueChanged.connect(lambda value: self.speed_combo.setCurrentIndex(int(value)))
    self.speed_combo.currentIndexChanged.connect(lambda index: self.speed_slider.setValue(int(index)))

    speed_control_row = QHBoxLayout()
    speed_control_row.setContentsMargins(0, 0, 0, 0)
    speed_control_row.setSpacing(9)
    speed_control_row.addWidget(self.speed_combo)
    speed_control_row.addWidget(self.speed_slider, stretch=1)
    speed_box.addLayout(speed_control_row)

    speed_scale = QHBoxLayout()
    speed_scale.setContentsMargins(0, 0, 0, 0)
    speed_scale.setSpacing(0)
    speed_scale.addSpacing(67)
    for text, align in (("0.1x", Qt.AlignmentFlag.AlignLeft), ("1x", Qt.AlignmentFlag.AlignCenter), ("4x", Qt.AlignmentFlag.AlignRight)):
        scale_lbl = QLabel(text)
        scale_lbl.setAlignment(align)
        scale_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; font-weight: 800; background: transparent;")
        speed_scale.addWidget(scale_lbl, stretch=1)
    speed_box.addLayout(speed_scale)
    loops_modes = QVBoxLayout()
    loops_modes.setContentsMargins(0, 0, 0, 0)
    loops_modes.setSpacing(3)

    loops_header = QHBoxLayout()
    loops_header.setContentsMargins(0, 0, 0, 0)
    loops_header.setSpacing(6)
    loops_header.addWidget(tiny_label("Loops"))
    loops_header.addStretch()
    loops_modes.addLayout(loops_header)

    loop_row = QHBoxLayout()
    loop_row.setContentsMargins(0, 0, 0, 0)
    loop_row.setSpacing(6)
    self.inf_check = QCheckBox("∞")
    self.inf_check.setObjectName("playback_inf_toggle")
    self.inf_check.setToolTip("Infinite loop")
    self.inf_check.setFixedSize(46, 26)
    self.inf_check.setStyleSheet(
        f"QCheckBox#playback_inf_toggle {{ color: {C['text']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding-left: 10px; "
        "font-size: 16px; font-weight: 800; }}"
        f"QCheckBox#playback_inf_toggle:hover {{ border-color: {C['border_light']}; }}"
        f"QCheckBox#playback_inf_toggle::indicator {{ width: 0px; height: 0px; }}"
        f"QCheckBox#playback_inf_toggle:checked {{ border-color: {C['accent']}; background-color: {C['accent_glow']}; }}"
    )
    loop_row.addWidget(self.inf_check)
    self.loops_spin = QSpinBox()
    self.loops_spin.setRange(1, 9999)
    self.loops_spin.setValue(1)
    self.loops_spin.setFixedHeight(26)
    self.loops_spin.setFixedWidth(56)
    self.loops_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    self.loops_spin.setStyleSheet(
        f"QSpinBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 4px 6px; "
        "font-size: 12px; font-weight: 800; }}"
        f"QSpinBox:hover {{ border-color: {C['accent_dim']}; }}"
        "QSpinBox::up-button, QSpinBox::down-button { border: none; background: transparent; width: 0px; }"
    )
    loop_row.addWidget(self.loops_spin)
    loop_row.addStretch()
    loops_modes.addLayout(loop_row)

    target_row = QHBoxLayout()
    target_row.setContentsMargins(0, 1, 0, 0)
    target_row.setSpacing(7)
    self.lock_window_combo = QComboBox()
    self.lock_window_combo.setObjectName("lock_window_combo")
    self.lock_window_combo.setToolTip("Target window for Lock to window")
    self.lock_window_combo.addItem("Choose target window", 0)
    self.lock_window_combo.setFixedHeight(26)
    # Keep the target selector readable without letting it consume the whole
    # bottom dock.  Wide layouts get a tidy capped selector, while compact
    # layouts can shrink it before the refresh/target icon cluster is squeezed.
    self.lock_window_combo.setMinimumWidth(132)
    self.lock_window_combo.setMaximumWidth(242)
    self.lock_window_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    self.lock_window_combo.setStyleSheet(
        f"QComboBox#lock_window_combo {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 3px 8px; "
        "font-size: 10px; font-weight: 850; }}"
        f"QComboBox#lock_window_combo:hover {{ border-color: {C['pause_cyan']}; }}"
        "QComboBox#lock_window_combo::drop-down { border: none; width: 14px; }"
    )
    self.lock_window_health = QLabel()
    self.lock_window_health.setObjectName("lock_window_health")
    self.lock_window_health.setFixedSize(10, 10)
    self.lock_window_health.setToolTip("Window target not selected")
    self.lock_window_health.setStyleSheet(
        f"QLabel#lock_window_health {{ background-color: {C['text_dark']}; "
        f"border: 1px solid {C['border']}; border-radius: 5px; }}"
    )
    target_row.addWidget(self.lock_window_health, alignment=Qt.AlignmentFlag.AlignVCenter)
    target_row.addWidget(self.lock_window_combo)
    # Push the icon tools away from the target selector when there is room,
    # but collapse the gap first on narrower window sizes.
    target_row.addStretch(1)

    lock_window_tools = QHBoxLayout()
    lock_window_tools.setContentsMargins(0, 0, 0, 0)
    lock_window_tools.setSpacing(7)

    def tiny_icon_btn(icon_name, tip, slot):
        btn = QPushButton()
        btn.setObjectName("lock_window_tool_btn")
        btn.setIcon(icon(icon_name, 14, C["pause_cyan"]))
        btn.setIconSize(QSize(14, 14))
        btn.setToolTip(tip)
        btn.setFixedSize(27, 26)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        btn.setStyleSheet(
            f"QPushButton#lock_window_tool_btn {{ color: {C['text']}; background-color: {C['bg_tertiary']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 0; }}"
            f"QPushButton#lock_window_tool_btn:hover {{ border-color: {C['pause_cyan']}; background-color: {C['bg_hover']}; }}"
        )
        return btn

    self.lock_window_refresh_btn = tiny_icon_btn("loop", "Refresh running windows", self.refresh_lock_windows)
    self.lock_window_pick_btn = tiny_icon_btn("target", "Pick foreground window after a short delay", self._capture_foreground_lock_window)
    lock_window_tools.addWidget(self.lock_window_refresh_btn)
    lock_window_tools.addWidget(self.lock_window_pick_btn)
    target_row.addLayout(lock_window_tools)

    self.lock_window_status = QLabel("No target window")
    self.lock_window_status.setObjectName("lock_window_status")
    self.lock_window_status.setFixedHeight(12)
    self.lock_window_status.setVisible(False)
    self.lock_window_status.setStyleSheet(
        f"color: {C['text_dark']}; font-size: 9px; font-weight: 750; background: transparent;"
    )

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(3)

    def add_mode_check(attr_name, label, icon_name, color, width, tooltip, checked=False, target_layout=None):
        frame = QFrame()
        frame.setObjectName(f"{attr_name}_chip")
        frame.setFixedSize(width, 26)
        frame.setProperty("checked", "true" if checked else "false")
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setToolTip(tooltip)
        frame.setStyleSheet(chip_style(f"{attr_name}_chip", color))
        frame_lo = QHBoxLayout(frame)
        frame_lo.setContentsMargins(6, 0, 6, 0)
        frame_lo.setSpacing(3)

        ico = QLabel()
        ico.setFixedSize(14, 14)
        frame_lo.addWidget(ico)

        check = QCheckBox(label)
        check.setObjectName("playback_mode_toggle")
        check.setToolTip(tooltip)
        check.setChecked(checked)
        check.setStyleSheet(
            f"QCheckBox#playback_mode_toggle {{ color: {C['text']}; font-size: 10px; font-weight: 850; spacing: 0px; }}"
            "QCheckBox#playback_mode_toggle::indicator { width: 0px; height: 0px; }"
        )
        frame_lo.addWidget(check, stretch=1)

        def refresh(is_checked):
            frame.setProperty("checked", "true" if is_checked else "false")
            active_col = color if is_checked else C["text_dim"]
            label_col = C["text"] if is_checked else C["text_dim"]
            ico.setPixmap(icon(icon_name, 14, active_col).pixmap(14, 14))
            check.setStyleSheet(
                f"QCheckBox#playback_mode_toggle {{ color: {label_col}; font-size: 10px; font-weight: 850; spacing: 0px; }}"
                "QCheckBox#playback_mode_toggle::indicator { width: 0px; height: 0px; }"
            )
            frame.style().unpolish(frame)
            frame.style().polish(frame)

        check.toggled.connect(refresh)
        refresh(checked)
        def _toggle_chip(event, cb=check):
            cb.toggle()
            event.accept()
        frame.mousePressEvent = _toggle_chip
        ico.mousePressEvent = _toggle_chip
        setattr(self, attr_name, check)
        if target_layout is not None:
            target_layout.insertWidget(0, frame)
        else:
            mode_row.addWidget(frame)

    add_mode_check("sim_check", "Sim", "play", C["accent"], 52, "Simulation mode")
    add_mode_check("human_check", "Humanize", "person", C["success"], 76, "Humanized movement curve", checked=True)
    add_mode_check("focus_check", "Window", "lock", C["pause_cyan"], 72, "Lock playback to the selected target window", target_layout=target_row)
    mode_row.addStretch()
    loops_modes.addLayout(mode_row)

    options_body.addLayout(loops_modes, stretch=1)
    options_body.addWidget(vertical_rule())
    options_body.addLayout(speed_box, stretch=2)
    opt_lo.addLayout(options_body)
    opt_lo.addSpacing(2)
    opt_lo.addLayout(target_row)
    opt_lo.addWidget(self.lock_window_status)
    top.addWidget(options_section, stretch=1)

    self.preflight_btn.setStyleSheet(
        f"QPushButton#preflight_btn {{ color: {C['accent']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; padding: 0; }}"
        f"QPushButton#preflight_btn:hover {{ border-color: {C['accent']}; background-color: {C['accent_glow']}; }}"
    )

    self.collapse_playback_btn = QPushButton("^")
    self.collapse_playback_btn.setToolTip("Collapse playback panel")
    self.collapse_playback_btn.setFixedSize(34, 34)
    self.collapse_playback_btn.setStyleSheet(
        f"QPushButton {{ color: {C['accent']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['accent_dim']}; border-radius: 9px; padding: 0; "
        "font-size: 14px; font-weight: 950; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
    )
    self.collapse_playback_btn.clicked.connect(lambda: self._set_playback_collapsed(True))

    playback_collapse_tools = QHBoxLayout()
    playback_collapse_tools.setContentsMargins(0, 0, 0, 0)
    playback_collapse_tools.setSpacing(4)
    self.playback_panel_lock_btn = QPushButton()
    self.playback_panel_lock_btn.setObjectName("playback_panel_lock_btn")
    self.playback_panel_lock_btn.setIcon(icon("lock", 15, C["text_dim"]))
    self.playback_panel_lock_btn.setIconSize(QSize(15, 15))
    self.playback_panel_lock_btn.setToolTip("Keep playback panel expanded")
    self.playback_panel_lock_btn.setFixedSize(30, 34)
    self.playback_panel_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.playback_panel_lock_btn.clicked.connect(self._toggle_playback_panel_lock)
    self.playback_panel_lock_btn.setStyleSheet(
        f"QPushButton#playback_panel_lock_btn {{ color: {C['text_dim']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 9px; padding: 0; }}"
        f"QPushButton#playback_panel_lock_btn:hover {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
    )
    playback_collapse_tools.addWidget(self.playback_panel_lock_btn)
    playback_collapse_tools.addWidget(self.collapse_playback_btn)
    top.addLayout(playback_collapse_tools)
    dlo.addLayout(top, stretch=1)

    bottom = QHBoxLayout()
    bottom.setContentsMargins(0, 0, 0, 0)
    bottom.setSpacing(6)

    progress_wrap = QFrame()
    progress_wrap.setObjectName("progress_wrap")
    progress_wrap.setMinimumWidth(300)
    progress_wrap.setMaximumWidth(16777215)
    progress_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    progress_wrap.setFixedHeight(38)
    progress_wrap.setStyleSheet(
        f"QFrame#progress_wrap {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; }}"
    )
    pw_lo = QHBoxLayout(progress_wrap)
    pw_lo.setContentsMargins(10, 4, 10, 4)
    pw_lo.setSpacing(8)
    self.progress_bar = QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setTextVisible(False)
    self.progress_bar.setFixedHeight(11)
    self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.progress_bar.setStyleSheet(
        f"QProgressBar {{ background-color: {C['lane']}; border: none; border-radius: 9px; }}"
        f"QProgressBar::chunk {{ background-color: {C['accent']}; border-radius: 9px; }}"
    )
    pw_lo.addWidget(self.progress_bar, stretch=1)
    self.progress_label = QLabel("0%")
    self.progress_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
    self.progress_label.setStyleSheet(
        f"color: {C['accent']}; font-size: 13px; font-weight: 900; min-width: 38px;"
    )
    pw_lo.addWidget(self.progress_label)
    bottom.addWidget(progress_wrap, stretch=1)

    self._stat_actions_w, self._stat_actions = self._make_stat_chip("bolt", "Played", "0", C["accent"], "Actions played this run")
    self._stat_loops_w, self._stat_loops = self._make_stat_chip("loop", "Loops", "0", C["neon_purple"], "Completed loops")
    self._stat_seq_w, self._stat_seq = self._make_stat_chip("delay", "Seq", "44.0s", C["neon_gold"], "Estimated sequence duration")
    self._stat_time_w, self._stat_time = self._make_stat_chip("clock", "Time", "0:00:00", C["accent"], "Estimated session time")
    for chip in (self._stat_actions_w, self._stat_loops_w, self._stat_seq_w, self._stat_time_w):
        bottom.addWidget(chip)
    dlo.addLayout(bottom)

    lo.addWidget(dock, stretch=1)
    self.playback_dock = dock

    self.playback_restore_btn = QPushButton("Show playback panel")
    self.playback_restore_btn.setToolTip("Restore playback controls")
    self.playback_restore_btn.setFixedHeight(30)
    self.playback_restore_btn.clicked.connect(lambda: self._set_playback_collapsed(False))
    self.playback_restore_btn.setVisible(False)
    lo.addWidget(self.playback_restore_btn)
    return panel
