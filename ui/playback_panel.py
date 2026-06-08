"""Playback panel construction for MacroForge main window.

The panel is built as a responsive command dock.  Wide layouts keep Playback,
Run Settings, and Stats in separate table-aligned cards.  Compact layouts hide
that separate Stats card and move the same stat chips into the bottom strip so
controls stay readable instead of overlapping.
"""

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
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
    panel.setFixedHeight(190)
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

    grid = QGridLayout(dock)
    grid.setContentsMargins(10, 7, 10, 7)
    grid.setHorizontalSpacing(9)
    grid.setVerticalSpacing(6)
    grid.setColumnStretch(0, 0)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(2, 0)
    grid.setRowStretch(0, 1)
    grid.setRowStretch(1, 0)

    def card(name):
        frame = QFrame()
        frame.setObjectName(name)
        frame.setStyleSheet(
            f"QFrame#{name} {{ background-color: {C['bg_secondary']}; "
            f"border: 1px solid {C['border']}; border-radius: 10px; }}"
            f"QFrame#{name} QLabel {{ background: transparent; border: none; }}"
        )
        return frame

    def title_row(text, icon_name, color):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        ico = QLabel()
        ico.setFixedSize(18, 18)
        ico.setPixmap(icon(icon_name, 17, color).pixmap(17, 17))
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

    def base_button(btn, obj, size, color=None):
        active = color or C['accent']
        btn.setObjectName(obj)
        btn.setFixedSize(*size)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton#{obj} {{ color: {C['text']}; background-color: {C['bg_tertiary']}; "
            f"border: 1px solid {C['border']}; border-radius: 8px; padding: 0; "
            "font-size: 11px; font-weight: 850; }}"
            f"QPushButton#{obj}:hover {{ border-color: {active}; background-color: {C['bg_hover']}; }}"
        )
        return btn

    def icon_button(obj, icon_name, tip, slot, size=(28, 28), color=None):
        btn = QPushButton()
        btn.setToolTip(tip)
        btn.setIcon(icon(icon_name, 14, color or C['pause_cyan']))
        btn.setIconSize(QSize(14, 14))
        base_button(btn, obj, size, color or C['pause_cyan'])
        btn.clicked.connect(slot)
        return btn

    def combo_style(obj, width, height=28, font_size=11):
        return (
            f"QComboBox#{obj} {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
            f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 3px 7px; "
            f"font-size: {font_size}px; font-weight: 850; min-width: {width}px; max-width: {width}px; min-height: {height}px; }}"
            f"QComboBox#{obj}:hover {{ border-color: {C['accent_dim']}; }}"
            "QComboBox::drop-down { border: none; width: 16px; }"
        )

    def spin_style(width, height=28):
        return (
            f"QSpinBox {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
            f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 3px 6px; "
            f"font-size: 12px; font-weight: 850; min-width: {width}px; max-width: {width}px; min-height: {height}px; }}"
            f"QSpinBox:hover {{ border-color: {C['accent_dim']}; }}"
            "QSpinBox::up-button, QSpinBox::down-button { border: none; background: transparent; width: 0px; }"
        )

    def checkbox_chip_style(name, active_color, checked=False):
        bg = C['accent_glow'] if checked else C['bg_tertiary']
        border = active_color if checked else C['border']
        return (
            f"QCheckBox#{name} {{ color: {C['text']}; background-color: {bg}; "
            f"border: 1px solid {border}; border-radius: 7px; padding: 0 7px; "
            "font-size: 10px; font-weight: 900; spacing: 0px; }}"
            "QCheckBox::indicator { width: 0px; height: 0px; }"
            f"QCheckBox#{name}:hover {{ border-color: {active_color}; background-color: {C['bg_hover']}; }}"
        )

    def utility_button_style():
        return (
            f"QPushButton {{ color: {C['accent']}; background-color: {C['bg_tertiary']}; "
            f"border: 1px solid {C['accent_dim']}; border-radius: 8px; padding: 0; "
            "font-size: 14px; font-weight: 950; }}"
            f"QPushButton:hover {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
        )

    # ------------------------------------------------------------------
    # Playback card: Play / Pause / Stop only.
    # ------------------------------------------------------------------
    play_section = card("playback_card")
    play_section.setFixedWidth(292)
    play_lo = QVBoxLayout(play_section)
    play_lo.setContentsMargins(12, 9, 12, 9)
    play_lo.setSpacing(8)
    play_lo.addLayout(title_row("PLAYBACK", "play", C['accent']))

    play_row = QHBoxLayout()
    play_row.setContentsMargins(0, 0, 0, 0)
    play_row.setSpacing(8)

    self.start_btn = QPushButton()
    self.start_btn.setIcon(icon("play", 18, C['success']))
    self.start_btn.setIconSize(QSize(18, 18))
    self.start_btn.setToolTip("Start playback (F9)")
    base_button(self.start_btn, "play_btn", (54, 38), C['success'])
    self.start_btn.setStyleSheet(
        f"QPushButton#play_btn {{ color: {C['success']}; background-color: #003c20; "
        f"border: 1px solid {C['success']}; border-radius: 8px; padding: 0; }}"
        f"QPushButton#play_btn:hover {{ background-color: #00552d; border-color: {C['success']}; }}"
    )
    self.start_btn.clicked.connect(self.start)
    play_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton()
    self.pause_btn.setIcon(icon("pause", 16, C['pause_cyan']))
    self.pause_btn.setIconSize(QSize(16, 16))
    self.pause_btn.setToolTip("Pause / resume playback (Esc)")
    base_button(self.pause_btn, "pause_btn", (54, 38), C['pause_cyan'])
    self.pause_btn.setEnabled(False)
    self.pause_btn.clicked.connect(self.engine.toggle_pause)
    play_row.addWidget(self.pause_btn)

    self.stop_btn = QPushButton()
    self.stop_btn.setIcon(icon("stop", 15, C['error']))
    self.stop_btn.setIconSize(QSize(15, 15))
    self.stop_btn.setToolTip("Stop playback")
    base_button(self.stop_btn, "stop_btn", (54, 38), C['error'])
    self.stop_btn.setEnabled(False)
    self.stop_btn.clicked.connect(self.stop)
    play_row.addWidget(self.stop_btn)
    play_row.addStretch()
    play_lo.addLayout(play_row)

    # Keep the old playback pre-flight button available for code that may look
    # it up, but do not show it next to Stop.
    self.preflight_btn = QPushButton()
    self.preflight_btn.setObjectName("preflight_btn")
    self.preflight_btn.setVisible(False)
    self.preflight_btn.clicked.connect(self.open_preflight_report)

    feedback_frame = QFrame()
    feedback_frame.setObjectName("playback_feedback_frame")
    feedback_frame.setFixedHeight(24)
    feedback_frame.setProperty("feedback_state", "ready")
    feedback_frame.setToolTip("Playback status")
    feedback_frame.setStyleSheet(
        f"QFrame#playback_feedback_frame {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {C['accent_glow']}, stop:1 {C['bg_tertiary']}); "
        f"border: 1px solid {C['accent_dim']}; border-radius: 7px; }}"
    )
    feedback_lo = QHBoxLayout(feedback_frame)
    feedback_lo.setContentsMargins(6, 0, 8, 0)
    feedback_lo.setSpacing(6)
    self.playback_feedback_icon = QLabel()
    self.playback_feedback_icon.setObjectName("playback_feedback_icon")
    self.playback_feedback_icon.setFixedSize(19, 18)
    self.playback_feedback_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.playback_feedback_icon.setPixmap(icon("bolt", 14, C['accent']).pixmap(14, 14))
    self.playback_feedback_icon.setStyleSheet(
        f"QLabel#playback_feedback_icon {{ background-color: {C['bg_secondary']}; "
        f"border: 1px solid {C['accent_dim']}; border-radius: 6px; }}"
    )
    feedback_lo.addWidget(self.playback_feedback_icon)
    self.playback_feedback_label = QLabel("Playback ready")
    self.playback_feedback_label.setObjectName("playback_feedback")
    self.playback_feedback_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.playback_feedback_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.playback_feedback_label.setStyleSheet(
        f"QLabel#playback_feedback {{ color: {C['accent']}; font-size: 10px; "
        "font-weight: 900; background: transparent; border: none; }}"
    )
    feedback_lo.addWidget(self.playback_feedback_label, stretch=1)
    self.playback_feedback_frame = feedback_frame
    play_lo.addWidget(feedback_frame)
    play_lo.addStretch()

    # ------------------------------------------------------------------
    # Run settings card.
    # ------------------------------------------------------------------
    settings_section = card("run_settings_card")
    settings_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    settings_lo = QVBoxLayout(settings_section)
    settings_lo.setContentsMargins(12, 9, 12, 9)
    settings_lo.setSpacing(6)

    settings_header = QHBoxLayout()
    settings_header.setContentsMargins(0, 0, 0, 0)
    settings_header.setSpacing(7)
    settings_header.addLayout(title_row("RUN SETTINGS", "settings", C['text_dim']))
    settings_lo.addLayout(settings_header)

    settings_grid = QGridLayout()
    settings_grid.setContentsMargins(0, 0, 0, 0)
    settings_grid.setHorizontalSpacing(13)
    settings_grid.setVerticalSpacing(5)
    settings_grid.setColumnStretch(0, 0)
    settings_grid.setColumnStretch(1, 0)
    settings_grid.setColumnStretch(2, 1)
    settings_lo.addLayout(settings_grid)
    settings_lo.addStretch()

    loops_group = QFrame()
    loops_group.setObjectName("loops_group")
    loops_group.setStyleSheet("QFrame#loops_group { background: transparent; border: none; }")
    loops_lo = QVBoxLayout(loops_group)
    loops_lo.setContentsMargins(0, 0, 0, 0)
    loops_lo.setSpacing(5)
    loops_lo.addWidget(tiny_label("Loops"))

    loop_row = QHBoxLayout()
    loop_row.setContentsMargins(0, 0, 0, 0)
    loop_row.setSpacing(6)
    self.inf_check = QCheckBox("∞")
    self.inf_check.setObjectName("playback_inf_toggle")
    self.inf_check.setToolTip("Infinite loop")
    self.inf_check.setFixedSize(42, 28)
    self.inf_check.setStyleSheet(
        f"QCheckBox#playback_inf_toggle {{ color: {C['text']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding-left: 10px; "
        "font-size: 15px; font-weight: 900; }}"
        "QCheckBox#playback_inf_toggle::indicator { width: 0px; height: 0px; }"
        f"QCheckBox#playback_inf_toggle:hover {{ border-color: {C['border_light']}; }}"
        f"QCheckBox#playback_inf_toggle:checked {{ border-color: {C['accent']}; background-color: {C['accent_glow']}; }}"
    )
    loop_row.addWidget(self.inf_check)

    self.loops_spin = QSpinBox()
    self.loops_spin.setRange(1, 9999)
    self.loops_spin.setValue(1)
    self.loops_spin.setFixedSize(56, 28)
    self.loops_spin.setStyleSheet(spin_style(56, 28))
    loop_row.addWidget(self.loops_spin)
    loop_row.addStretch()
    loops_lo.addLayout(loop_row)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(6)

    def mode_check(attr_name, label, icon_name, color, width, tooltip, checked=False):
        check = QCheckBox(label)
        check.setObjectName(attr_name)
        check.setToolTip(tooltip)
        check.setChecked(checked)
        check.setFixedSize(width, 24)
        check.setCursor(Qt.CursorShape.PointingHandCursor)

        def refresh(is_checked):
            check.setStyleSheet(checkbox_chip_style(attr_name, color, is_checked))
            check.setIcon(icon(icon_name, 13, color if is_checked else C['text_dim']))
            check.setIconSize(QSize(13, 13))

        check.toggled.connect(refresh)
        refresh(checked)
        setattr(self, attr_name, check)
        return check

    mode_row.addWidget(mode_check("sim_check", "Sim", "play", C['accent'], 54, "Simulation mode"))
    mode_row.addWidget(mode_check("human_check", "Human", "person", C['success'], 74, "Humanized movement curve", checked=True))
    mode_row.addStretch()
    loops_lo.addLayout(mode_row)

    speed_group = QFrame()
    speed_group.setObjectName("speed_group")
    speed_group.setStyleSheet("QFrame#speed_group { background: transparent; border: none; }")
    speed_lo = QVBoxLayout(speed_group)
    speed_lo.setContentsMargins(0, 0, 0, 0)
    speed_lo.setSpacing(5)
    speed_lo.addWidget(tiny_label("Speed"))
    self.speed_combo = QComboBox()
    self.speed_combo.setObjectName("speed_combo")
    self.speed_combo.addItems(["0.1x", "0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "3.0x", "4.0x"])
    self.speed_combo.setCurrentText("1.0x")
    self.speed_combo.currentTextChanged.connect(self._on_speed_change)
    self.speed_combo.setFixedSize(96, 30)
    self.speed_combo.setStyleSheet(combo_style("speed_combo", 96, 30, 12))
    speed_lo.addWidget(self.speed_combo)
    speed_lo.addStretch()

    # Hidden compatibility slider: the visible speed control is now the combo box only.
    self.speed_slider = QSlider(Qt.Orientation.Horizontal)
    self.speed_slider.setObjectName("playback_speed_slider")
    self.speed_slider.setRange(0, self.speed_combo.count() - 1)
    self.speed_slider.setValue(self.speed_combo.currentIndex())
    self.speed_slider.valueChanged.connect(lambda value: self.speed_combo.setCurrentIndex(int(value)))
    self.speed_combo.currentIndexChanged.connect(lambda index: self.speed_slider.setValue(int(index)))
    self.speed_slider.setVisible(False)

    target_group = QFrame()
    target_group.setObjectName("target_group")
    target_group.setStyleSheet("QFrame#target_group { background: transparent; border: none; }")
    target_lo = QVBoxLayout(target_group)
    target_lo.setContentsMargins(0, 0, 0, 0)
    target_lo.setSpacing(5)
    target_lo.addWidget(tiny_label("Target"))

    target_controls = QHBoxLayout()
    target_controls.setContentsMargins(0, 0, 0, 0)
    target_controls.setSpacing(6)

    self.focus_check = QCheckBox("ON")
    self.focus_check.setObjectName("focus_check")
    self.focus_check.setToolTip("Toggle target-window lock on/off")
    self.focus_check.setChecked(False)
    self.focus_check.setFixedSize(46, 26)
    self.focus_check.setCursor(Qt.CursorShape.PointingHandCursor)

    def refresh_focus_text(checked):
        self.focus_check.setText("ON" if checked else "OFF")
        self.focus_check.setStyleSheet(checkbox_chip_style("focus_check", C['pause_cyan'] if checked else C['text_dim'], checked))

    self.focus_check.toggled.connect(refresh_focus_text)
    refresh_focus_text(False)
    target_controls.addWidget(self.focus_check)

    self.lock_window_combo = QComboBox()
    self.lock_window_combo.setObjectName("lock_window_combo")
    self.lock_window_combo.setToolTip("Target window for Lock to window")
    self.lock_window_combo.addItem("Target", 0)
    self.lock_window_combo.setFixedSize(112, 28)
    self.lock_window_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    self.lock_window_combo.setStyleSheet(
        f"QComboBox#lock_window_combo {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 3px 7px; "
        "font-size: 10px; font-weight: 850; }}"
        f"QComboBox#lock_window_combo:hover {{ border-color: {C['pause_cyan']}; }}"
        "QComboBox#lock_window_combo::drop-down { border: none; width: 13px; }"
    )
    target_controls.addWidget(self.lock_window_combo)

    self.lock_window_refresh_btn = icon_button("lock_window_tool_btn", "loop", "Refresh running windows", self.refresh_lock_windows, (28, 28), C['pause_cyan'])
    self.lock_window_pick_btn = icon_button("lock_window_tool_btn", "target", "Pick foreground window after a short delay", self._capture_foreground_lock_window, (28, 28), C['pause_cyan'])
    target_controls.addWidget(self.lock_window_refresh_btn)
    target_controls.addWidget(self.lock_window_pick_btn)
    target_controls.addStretch()
    target_lo.addLayout(target_controls)

    self.lock_window_health = QLabel()
    self.lock_window_health.setObjectName("lock_window_health")
    self.lock_window_health.setFixedSize(9, 9)
    self.lock_window_health.setToolTip("Window target not selected")
    self.lock_window_health.setVisible(False)
    self.lock_window_health.setStyleSheet(
        f"QLabel#lock_window_health {{ background-color: {C['text_dark']}; "
        f"border: 1px solid {C['border']}; border-radius: 5px; }}"
    )

    self.lock_window_status = QLabel("No target window")
    self.lock_window_status.setObjectName("lock_window_status")
    self.lock_window_status.setFixedHeight(12)
    self.lock_window_status.setVisible(False)
    self.lock_window_status.setStyleSheet(
        f"color: {C['text_dark']}; font-size: 9px; font-weight: 750; background: transparent;"
    )

    settings_grid.addWidget(loops_group, 0, 0, 2, 1, alignment=Qt.AlignmentFlag.AlignTop)
    settings_grid.addWidget(speed_group, 0, 1, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
    settings_grid.addWidget(target_group, 0, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)

    # ------------------------------------------------------------------
    # Utility lock/collapse cluster, moved between Settings and Stats based
    # on width.  Compact mode keeps it in Settings; stretched keeps it in Stats.
    # ------------------------------------------------------------------
    utility_holder = QFrame()
    utility_holder.setObjectName("playback_utility_holder")
    utility_holder.setStyleSheet("QFrame#playback_utility_holder { background: transparent; border: none; }")
    utility_lo = QHBoxLayout(utility_holder)
    utility_lo.setContentsMargins(0, 0, 0, 0)
    utility_lo.setSpacing(6)

    self.playback_panel_lock_btn = QPushButton()
    self.playback_panel_lock_btn.setObjectName("playback_panel_lock_btn")
    self.playback_panel_lock_btn.setIcon(icon("lock", 14, C['text_dim']))
    self.playback_panel_lock_btn.setIconSize(QSize(14, 14))
    self.playback_panel_lock_btn.setToolTip("Keep playback panel expanded")
    self.playback_panel_lock_btn.setFixedSize(30, 32)
    self.playback_panel_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.playback_panel_lock_btn.clicked.connect(self._toggle_playback_panel_lock)
    self.playback_panel_lock_btn.setStyleSheet(
        f"QPushButton#playback_panel_lock_btn {{ color: {C['text_dim']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; padding: 0; }}"
        f"QPushButton#playback_panel_lock_btn:hover {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
    )
    utility_lo.addWidget(self.playback_panel_lock_btn)

    self.collapse_playback_btn = QPushButton("^")
    self.collapse_playback_btn.setToolTip("Collapse playback panel")
    self.collapse_playback_btn.setFixedSize(30, 32)
    self.collapse_playback_btn.setStyleSheet(utility_button_style())
    self.collapse_playback_btn.clicked.connect(lambda: self._set_playback_collapsed(True))
    utility_lo.addWidget(self.collapse_playback_btn)

    # ------------------------------------------------------------------
    # Stats card.  Uses the existing old-style icon + value stat chips.
    # ------------------------------------------------------------------
    stats_section = card("stats_card")
    stats_section.setFixedWidth(310)
    stats_lo = QVBoxLayout(stats_section)
    stats_lo.setContentsMargins(12, 9, 12, 9)
    stats_lo.setSpacing(7)
    stats_header = QHBoxLayout()
    stats_header.setContentsMargins(0, 0, 0, 0)
    stats_header.setSpacing(7)
    stats_header.addLayout(title_row("STATS", "bolt", C['text_dim']))
    stats_lo.addLayout(stats_header)

    stats_body = QHBoxLayout()
    stats_body.setContentsMargins(0, 0, 0, 0)
    stats_body.setSpacing(6)
    stats_lo.addLayout(stats_body)
    stats_lo.addStretch()

    self._stat_actions_w, self._stat_actions = self._make_stat_chip("bolt", "Played", "0", C['accent'], "Actions played this run")
    self._stat_loops_w, self._stat_loops = self._make_stat_chip("loop", "Loops", "0", C['neon_purple'], "Completed loops")
    self._stat_seq_w, self._stat_seq = self._make_stat_chip("delay", "Seq", "44.0s", C['neon_gold'], "Estimated sequence duration")
    self._stat_time_w, self._stat_time = self._make_stat_chip("clock", "Time", "0:00:00", C['accent'], "Estimated session time")
    for chip in (self._stat_actions_w, self._stat_loops_w, self._stat_seq_w, self._stat_time_w):
        chip.setFixedHeight(31)

    # ------------------------------------------------------------------
    # Bottom progress + compact stat strip.
    # ------------------------------------------------------------------
    bottom_strip = QFrame()
    bottom_strip.setObjectName("progress_stats_strip")
    bottom_strip.setFixedHeight(38)
    bottom_strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    bottom_strip.setStyleSheet(
        f"QFrame#progress_stats_strip {{ background-color: {C['bg_secondary']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; }}"
        f"QFrame#progress_stats_strip QLabel {{ background: transparent; border: none; }}"
    )
    bottom_lo = QHBoxLayout(bottom_strip)
    bottom_lo.setContentsMargins(10, 4, 10, 4)
    bottom_lo.setSpacing(8)
    progress_title = QLabel("Progress")
    progress_title.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px; font-weight: 850; background: transparent;")
    bottom_lo.addWidget(progress_title)

    self.progress_bar = QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setTextVisible(False)
    self.progress_bar.setFixedHeight(10)
    self.progress_bar.setMinimumWidth(160)
    self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.progress_bar.setStyleSheet(
        f"QProgressBar {{ background-color: {C['lane']}; border: none; border-radius: 6px; }}"
        f"QProgressBar::chunk {{ background-color: {C['accent']}; border-radius: 6px; }}"
    )
    bottom_lo.addWidget(self.progress_bar, stretch=1)

    self.progress_label = QLabel("0%")
    self.progress_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
    self.progress_label.setFixedWidth(36)
    self.progress_label.setStyleSheet(f"color: {C['accent']}; font-size: 12px; font-weight: 900;")
    bottom_lo.addWidget(self.progress_label)

    bottom_stats = QHBoxLayout()
    bottom_stats.setContentsMargins(0, 0, 0, 0)
    bottom_stats.setSpacing(6)
    bottom_lo.addLayout(bottom_stats)

    # Place widgets in the responsive grid.
    grid.addWidget(play_section, 0, 0)
    grid.addWidget(settings_section, 0, 1)
    grid.addWidget(stats_section, 0, 2, 2, 1)
    grid.addWidget(bottom_strip, 1, 0, 1, 2)

    layout_state = {"compact": None, "stats_parent": None, "utility_parent": None, "target_pos": None}
    stat_widgets = (self._stat_actions_w, self._stat_loops_w, self._stat_seq_w, self._stat_time_w)

    def remove_from_layout(layout, widget):
        try:
            layout.removeWidget(widget)
        except Exception:
            pass

    def move_stats(to_compact):
        target_layout = bottom_stats if to_compact else stats_body
        target_name = "compact" if to_compact else "stats"
        if layout_state["stats_parent"] == target_name:
            return
        for chip in stat_widgets:
            remove_from_layout(bottom_stats, chip)
            remove_from_layout(stats_body, chip)
            target_layout.addWidget(chip)
        layout_state["stats_parent"] = target_name

    def move_utility(to_compact):
        target_layout = settings_header if to_compact else stats_header
        target_name = "settings" if to_compact else "stats"
        if layout_state["utility_parent"] == target_name:
            return
        remove_from_layout(settings_header, utility_holder)
        remove_from_layout(stats_header, utility_holder)
        target_layout.addWidget(utility_holder)
        layout_state["utility_parent"] = target_name

    def move_target(to_compact):
        target_name = "compact" if to_compact else "wide"
        if layout_state["target_pos"] == target_name:
            return
        settings_grid.removeWidget(target_group)
        if to_compact:
            settings_grid.addWidget(target_group, 1, 1, 1, 2, alignment=Qt.AlignmentFlag.AlignTop)
            target_group.setMaximumWidth(245)
            self.lock_window_combo.setFixedWidth(104)
        else:
            settings_grid.addWidget(target_group, 0, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignTop)
            target_group.setMaximumWidth(260)
            self.lock_window_combo.setFixedWidth(112)
        layout_state["target_pos"] = target_name

    def update_layout_mode():
        width = dock.width() or panel.width()
        compact = width < 1040
        if layout_state["compact"] == compact:
            return
        stats_section.setVisible(not compact)
        move_stats(compact)
        move_utility(compact)
        move_target(compact)
        if compact:
            panel.setFixedHeight(190)
            settings_grid.setHorizontalSpacing(11)
            bottom_strip.setFixedHeight(38)
        else:
            panel.setFixedHeight(190)
            settings_grid.setHorizontalSpacing(14)
            bottom_strip.setFixedHeight(38)
        layout_state["compact"] = compact

    old_resize_event = dock.resizeEvent

    def dock_resize_event(event):
        old_resize_event(event)
        update_layout_mode()

    dock.resizeEvent = dock_resize_event
    QTimer.singleShot(0, update_layout_mode)

    lo.addWidget(dock, stretch=1)
    self.playback_dock = dock

    self.playback_restore_btn = QPushButton("Show playback panel")
    self.playback_restore_btn.setToolTip("Restore playback controls")
    self.playback_restore_btn.setFixedHeight(30)
    self.playback_restore_btn.clicked.connect(lambda: self._set_playback_collapsed(False))
    self.playback_restore_btn.setVisible(False)
    lo.addWidget(self.playback_restore_btn)
    return panel
