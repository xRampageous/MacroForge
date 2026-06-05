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
    panel.setFixedHeight(175)
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
    dlo.setContentsMargins(10, 6, 10, 6)
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
    top.setSpacing(10)

    play_section = QFrame()
    play_section.setObjectName("playback_block")
    play_section.setFixedWidth(204)
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
    self.start_btn.setFixedSize(52, 38)
    self.start_btn.clicked.connect(self.start)
    play_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton()
    self.pause_btn.setObjectName("pause_btn")
    self.pause_btn.setIcon(icon("pause", 17, C["pause_cyan"]))
    self.pause_btn.setIconSize(QSize(17, 17))
    self.pause_btn.setToolTip("Pause / resume playback (Esc)")
    self.pause_btn.setFixedSize(52, 38)
    self.pause_btn.setEnabled(False)
    self.pause_btn.clicked.connect(self.engine.toggle_pause)
    play_row.addWidget(self.pause_btn)

    self.stop_btn = QPushButton()
    self.stop_btn.setObjectName("stop_btn")
    self.stop_btn.setIcon(icon("stop", 16, C["error"]))
    self.stop_btn.setIconSize(QSize(16, 16))
    self.stop_btn.setToolTip("Stop playback")
    self.stop_btn.setFixedSize(52, 38)
    self.stop_btn.setEnabled(False)
    self.stop_btn.clicked.connect(self.stop)
    play_row.addWidget(self.stop_btn)
    play_row.addStretch()
    play_lo.addLayout(play_row)

    feedback_frame = QFrame()
    feedback_frame.setObjectName("playback_feedback_frame")
    feedback_frame.setFixedSize(204, 26)
    feedback_frame.setToolTip("Playback status")
    feedback_frame.setStyleSheet(
        f"QFrame#playback_feedback_frame {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['accent_dim']}; border-radius: 7px; }}"
    )
    feedback_lo = QHBoxLayout(feedback_frame)
    feedback_lo.setContentsMargins(8, 0, 8, 0)
    feedback_lo.setSpacing(6)
    self.playback_feedback_icon = QLabel()
    self.playback_feedback_icon.setObjectName("playback_feedback_icon")
    self.playback_feedback_icon.setFixedSize(15, 15)
    self.playback_feedback_icon.setPixmap(icon("bolt", 15, C["accent"]).pixmap(15, 15))
    feedback_lo.addWidget(self.playback_feedback_icon)

    self.playback_feedback_label = QLabel("Playback ready")
    self.playback_feedback_label.setObjectName("playback_feedback")
    self.playback_feedback_label.setFixedHeight(22)
    self.playback_feedback_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.playback_feedback_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.playback_feedback_label.setToolTip("Playback status")
    self.playback_feedback_label.setStyleSheet(
        f"QLabel#playback_feedback {{ color: {C['accent']}; "
        "font-size: 11px; font-weight: 850; background: transparent; border: none; }}"
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
    options_body.setSpacing(10)

    speed_box = QVBoxLayout()
    speed_box.setContentsMargins(0, 0, 0, 0)
    speed_box.setSpacing(3)
    speed_box.addWidget(tiny_label("Speed"))
    self.speed_combo = QComboBox()
    self.speed_combo.addItems(["0.1x", "0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "3.0x", "4.0x"])
    self.speed_combo.setCurrentText("1.0x")
    self.speed_combo.currentTextChanged.connect(self._on_speed_change)
    self.speed_combo.setFixedHeight(30)
    self.speed_combo.setFixedWidth(50)
    self.speed_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    self.speed_combo.setStyleSheet(
        f"QComboBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 4px 4px; "
        "font-size: 12px; font-weight: 800; }}"
        f"QComboBox:hover {{ border-color: {C['accent_dim']}; }}"
        "QComboBox::drop-down { border: none; width: 0px; }"
        "QComboBox::down-arrow { image: none; width: 0px; height: 0px; }"
    )
    speed_box.addWidget(self.speed_combo)

    self.speed_slider = QSlider(Qt.Orientation.Horizontal)
    self.speed_slider.setObjectName("playback_speed_slider")
    self.speed_slider.setRange(0, self.speed_combo.count() - 1)
    self.speed_slider.setValue(self.speed_combo.currentIndex())
    self.speed_slider.setTickInterval(1)
    self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    self.speed_slider.setFixedHeight(20)
    self.speed_slider.setStyleSheet(
        f"QSlider#playback_speed_slider::groove:horizontal {{ height: 6px; background: {C['lane']}; border-radius: 3px; }}"
        f"QSlider#playback_speed_slider::sub-page:horizontal {{ background: {C['accent']}; border-radius: 3px; }}"
        f"QSlider#playback_speed_slider::handle:horizontal {{ background: {C['accent']}; width: 16px; height: 16px; "
        f"border-radius: 8px; margin: -5px 0; }}"
        f"QSlider#playback_speed_slider::handle:horizontal:hover {{ background: {C['accent_hover']}; }}"
    )
    self.speed_slider.valueChanged.connect(lambda value: self.speed_combo.setCurrentIndex(int(value)))
    self.speed_combo.currentIndexChanged.connect(lambda index: self.speed_slider.setValue(int(index)))
    speed_box.addWidget(self.speed_slider)

    speed_scale = QHBoxLayout()
    speed_scale.setContentsMargins(0, 0, 0, 0)
    speed_scale.setSpacing(0)
    for text, align in (("0.1x", Qt.AlignmentFlag.AlignLeft), ("1x", Qt.AlignmentFlag.AlignCenter), ("4x", Qt.AlignmentFlag.AlignRight)):
        scale_lbl = QLabel(text)
        scale_lbl.setAlignment(align)
        scale_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; font-weight: 800; background: transparent;")
        speed_scale.addWidget(scale_lbl, stretch=1)
    speed_box.addLayout(speed_scale)
    options_body.addLayout(speed_box, stretch=2)
    options_body.addWidget(vertical_rule())

    loops_modes = QVBoxLayout()
    loops_modes.setContentsMargins(0, 0, 0, 0)
    loops_modes.setSpacing(5)

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
    self.inf_check.setFixedSize(52, 30)
    self.inf_check.setStyleSheet(
        f"QCheckBox#playback_inf_toggle {{ color: {C['text']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding-left: 12px; "
        "font-size: 18px; font-weight: 800; }}"
        f"QCheckBox#playback_inf_toggle:hover {{ border-color: {C['border_light']}; }}"
        f"QCheckBox#playback_inf_toggle::indicator {{ width: 0px; height: 0px; }}"
        f"QCheckBox#playback_inf_toggle:checked {{ border-color: {C['accent']}; background-color: {C['accent_glow']}; }}"
    )
    loop_row.addWidget(self.inf_check)
    self.loops_spin = QSpinBox()
    self.loops_spin.setRange(1, 9999)
    self.loops_spin.setValue(1)
    self.loops_spin.setFixedHeight(30)
    self.loops_spin.setFixedWidth(60)
    self.loops_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    self.loops_spin.setStyleSheet(
        f"QSpinBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 4px 6px; "
        "font-size: 12px; font-weight: 800; }}"
        f"QSpinBox:hover {{ border-color: {C['accent_dim']}; }}"
        "QSpinBox::up-button, QSpinBox::down-button { border: none; background: transparent; width: 0px; }"
    )
    loop_count = QVBoxLayout()
    loop_count.setContentsMargins(0, 0, 0, 0)
    loop_count.setSpacing(2)
    loop_count.addWidget(self.loops_spin)
    loops_hint = QLabel("# loops")
    loops_hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px; font-weight: 750; background: transparent;")
    loop_count.addWidget(loops_hint)
    loop_row.addLayout(loop_count, stretch=1)
    loops_modes.addLayout(loop_row)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(5)

    def add_mode_check(attr_name, label, icon_name, color, width, tooltip, checked=False):
        frame = QFrame()
        frame.setObjectName(f"{attr_name}_chip")
        frame.setFixedSize(width, 30)
        frame.setProperty("checked", "true" if checked else "false")
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setToolTip(tooltip)
        frame.setStyleSheet(chip_style(f"{attr_name}_chip", color))
        frame_lo = QHBoxLayout(frame)
        frame_lo.setContentsMargins(7, 0, 7, 0)
        frame_lo.setSpacing(4)

        ico = QLabel()
        ico.setFixedSize(16, 16)
        frame_lo.addWidget(ico)

        check = QCheckBox(label)
        check.setObjectName("playback_mode_toggle")
        check.setToolTip(tooltip)
        check.setChecked(checked)
        check.setStyleSheet(
            f"QCheckBox#playback_mode_toggle {{ color: {C['text']}; font-size: 11px; font-weight: 850; spacing: 0px; }}"
            "QCheckBox#playback_mode_toggle::indicator { width: 0px; height: 0px; }"
        )
        frame_lo.addWidget(check, stretch=1)

        def refresh(is_checked):
            frame.setProperty("checked", "true" if is_checked else "false")
            active_col = color if is_checked else C["text_dim"]
            label_col = C["text"] if is_checked else C["text_dim"]
            ico.setPixmap(icon(icon_name, 16, active_col).pixmap(16, 16))
            check.setStyleSheet(
                f"QCheckBox#playback_mode_toggle {{ color: {label_col}; font-size: 11px; font-weight: 850; spacing: 0px; }}"
                "QCheckBox#playback_mode_toggle::indicator { width: 0px; height: 0px; }"
            )
            frame.style().unpolish(frame)
            frame.style().polish(frame)

        check.toggled.connect(refresh)
        refresh(checked)
        frame.mousePressEvent = lambda event, cb=check: cb.toggle()
        setattr(self, attr_name, check)
        mode_row.addWidget(frame)

    add_mode_check("sim_check", "Sim", "settings", C["accent"], 60, "Simulation mode")
    add_mode_check("human_check", "Human", "target", C["success"], 72, "Humanized movement curve", checked=True)
    add_mode_check("focus_check", "Lock", "lock", C["pause_cyan"], 66, "Refocus the locked window before each action")
    mode_row.addStretch()
    loops_modes.addLayout(mode_row)
    options_body.addLayout(loops_modes, stretch=2)
    opt_lo.addLayout(options_body)
    top.addWidget(options_section, stretch=1)

    self.bottom_panel_lock_btn = QPushButton(panel)
    self.bottom_panel_lock_btn.setObjectName("panel_lock_btn")
    self.bottom_panel_lock_btn.setToolTip("Lock bottom panel height")
    self.bottom_panel_lock_btn.setFixedSize(1, 1)
    self.bottom_panel_lock_btn.clicked.connect(self._toggle_bottom_panel_lock)
    self.bottom_panel_lock_btn.setVisible(False)

    self.collapse_playback_btn = QPushButton("^")
    self.collapse_playback_btn.setToolTip("Collapse playback panel")
    self.collapse_playback_btn.setFixedSize(42, 40)
    self.collapse_playback_btn.setStyleSheet(
        f"QPushButton {{ color: {C['accent']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['accent_dim']}; border-radius: 9px; padding: 0; "
        "font-size: 16px; font-weight: 950; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
    )
    self.collapse_playback_btn.clicked.connect(lambda: self._set_playback_collapsed(True))
    top.addWidget(self.collapse_playback_btn, alignment=Qt.AlignmentFlag.AlignTop)
    dlo.addLayout(top, stretch=1)

    bottom = QHBoxLayout()
    bottom.setContentsMargins(0, 0, 0, 0)
    bottom.setSpacing(6)

    progress_wrap = QFrame()
    progress_wrap.setObjectName("progress_wrap")
    progress_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    progress_wrap.setFixedHeight(36)
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
    self.progress_bar.setFixedHeight(9)
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
