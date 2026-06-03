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
    panel.setFixedHeight(188)
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    panel.setStyleSheet(f"QFrame#mf3_playback_panel {{ background-color: {C['bg']}; border: none; }}")

    lo = QVBoxLayout(panel)
    lo.setContentsMargins(8, 4, 8, 8)
    lo.setSpacing(0)

    dock = QFrame()
    dock.setObjectName("mf3_playback_dock")
    dock.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    dock.setStyleSheet(
        f"QFrame#mf3_playback_dock {{ background-color: {C['bg_card']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; }}"
    )
    dlo = QVBoxLayout(dock)
    dlo.setContentsMargins(10, 9, 10, 9)
    dlo.setSpacing(8)

    def section_title(text, icon_name, color):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        ico = QLabel()
        ico.setPixmap(icon(icon_name, 15, color).pixmap(15, 15))
        ico.setFixedSize(16, 16)
        row.addWidget(ico)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 12px; font-weight: 900; "
            "letter-spacing: 0.4px; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch()
        return row

    def tiny_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; font-weight: 800; background: transparent;"
        )
        return lbl

    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(10)

    play_section = QFrame()
    play_section.setObjectName("playback_block")
    play_section.setFixedWidth(220)
    play_section.setStyleSheet("QFrame#playback_block { background: transparent; border: none; }")
    play_lo = QVBoxLayout(play_section)
    play_lo.setContentsMargins(0, 0, 0, 0)
    play_lo.setSpacing(8)
    play_lo.addLayout(section_title("PLAYBACK", "play", C["accent"]))

    play_row = QHBoxLayout()
    play_row.setContentsMargins(0, 0, 0, 0)
    play_row.setSpacing(8)
    self.start_btn = QPushButton()
    self.start_btn.setObjectName("play_btn")
    self.start_btn.setIcon(icon("play", 18, C["success"]))
    self.start_btn.setIconSize(QSize(18, 18))
    self.start_btn.setToolTip("Start playback (F9)")
    self.start_btn.setFixedSize(58, 42)
    self.start_btn.clicked.connect(self.start)
    play_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton()
    self.pause_btn.setObjectName("pause_btn")
    self.pause_btn.setIcon(icon("pause", 17, C["pause_cyan"]))
    self.pause_btn.setIconSize(QSize(17, 17))
    self.pause_btn.setToolTip("Pause / resume playback (Esc)")
    self.pause_btn.setFixedSize(58, 42)
    self.pause_btn.setEnabled(False)
    self.pause_btn.clicked.connect(self.engine.toggle_pause)
    play_row.addWidget(self.pause_btn)

    self.stop_btn = QPushButton()
    self.stop_btn.setObjectName("stop_btn")
    self.stop_btn.setIcon(icon("stop", 16, C["error"]))
    self.stop_btn.setIconSize(QSize(16, 16))
    self.stop_btn.setToolTip("Stop playback")
    self.stop_btn.setFixedSize(58, 42)
    self.stop_btn.setEnabled(False)
    self.stop_btn.clicked.connect(self.stop)
    play_row.addWidget(self.stop_btn)
    play_row.addStretch()
    play_lo.addLayout(play_row)

    self.playback_feedback_label = QLabel("Playback ready")
    self.playback_feedback_label.setObjectName("playback_feedback")
    self.playback_feedback_label.setFixedHeight(34)
    self.playback_feedback_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.playback_feedback_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.playback_feedback_label.setToolTip("Playback status")
    self.playback_feedback_label.setStyleSheet(
        f"QLabel#playback_feedback {{ background-color: {C['bg_tertiary']}; color: {C['accent']}; "
        f"border: 1px solid {C['accent_dim']}; border-radius: 8px; padding: 5px 10px; "
        "font-size: 12px; font-weight: 850; }}"
    )
    play_lo.addWidget(self.playback_feedback_label)
    top.addWidget(play_section)

    options_section = QFrame()
    options_section.setObjectName("options_block")
    options_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    options_section.setStyleSheet("QFrame#options_block { background: transparent; border: none; }")
    opt_lo = QVBoxLayout(options_section)
    opt_lo.setContentsMargins(0, 0, 0, 0)
    opt_lo.setSpacing(7)
    opt_lo.addLayout(section_title("OPTIONS", "settings", C["text_dim"]))

    speed_loop_row = QHBoxLayout()
    speed_loop_row.setContentsMargins(0, 0, 0, 0)
    speed_loop_row.setSpacing(8)

    speed_box = QVBoxLayout()
    speed_box.setContentsMargins(0, 0, 0, 0)
    speed_box.setSpacing(3)
    speed_box.addWidget(tiny_label("Speed"))
    self.speed_combo = QComboBox()
    self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "3.0x"])
    self.speed_combo.setCurrentIndex(3)
    self.speed_combo.currentTextChanged.connect(self._on_speed_change)
    self.speed_combo.setFixedHeight(34)
    self.speed_combo.setMinimumWidth(112)
    self.speed_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    speed_box.addWidget(self.speed_combo)
    speed_loop_row.addLayout(speed_box, stretch=2)

    loops_box = QVBoxLayout()
    loops_box.setContentsMargins(0, 0, 0, 0)
    loops_box.setSpacing(3)
    loops_box.addWidget(tiny_label("Loops"))
    loop_row = QHBoxLayout()
    loop_row.setContentsMargins(0, 0, 0, 0)
    loop_row.setSpacing(5)
    self.inf_check = QCheckBox("∞")
    self.inf_check.setObjectName("pill_check")
    self.inf_check.setToolTip("Infinite loop")
    self.inf_check.setFixedSize(48, 34)
    loop_row.addWidget(self.inf_check)
    self.loops_spin = QSpinBox()
    self.loops_spin.setRange(1, 9999)
    self.loops_spin.setValue(1)
    self.loops_spin.setFixedHeight(34)
    self.loops_spin.setMinimumWidth(70)
    loop_row.addWidget(self.loops_spin)
    loops_box.addLayout(loop_row)
    speed_loop_row.addLayout(loops_box, stretch=1)
    opt_lo.addLayout(speed_loop_row)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(6)
    self.sim_check = QCheckBox("Sim")
    self.sim_check.setObjectName("pill_check")
    self.sim_check.setToolTip("Simulation mode")
    self.sim_check.setFixedSize(64, 32)
    mode_row.addWidget(self.sim_check)
    self.human_check = QCheckBox("Human")
    self.human_check.setObjectName("pill_check")
    self.human_check.setToolTip("Humanized movement curve")
    self.human_check.setFixedSize(82, 32)
    self.human_check.setChecked(True)
    mode_row.addWidget(self.human_check)
    self.focus_check = QCheckBox("Lock")
    self.focus_check.setObjectName("pill_check")
    self.focus_check.setToolTip("Keep playback targeted to the captured window")
    self.focus_check.setFixedSize(70, 32)
    mode_row.addWidget(self.focus_check)
    mode_row.addStretch()
    opt_lo.addLayout(mode_row)
    top.addWidget(options_section, stretch=1)

    self.collapse_playback_btn = QPushButton("Hide  ^")
    self.collapse_playback_btn.setToolTip("Collapse playback panel")
    self.collapse_playback_btn.setFixedSize(68, 34)
    self.collapse_playback_btn.setStyleSheet(
        f"QPushButton {{ color: {C['accent']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['accent_dim']}; border-radius: 10px; padding: 0 9px; "
        "font-size: 12px; font-weight: 850; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
    )
    self.collapse_playback_btn.clicked.connect(lambda: self._set_playback_collapsed(True))
    top.addWidget(self.collapse_playback_btn, alignment=Qt.AlignmentFlag.AlignTop)
    dlo.addLayout(top)

    bottom = QHBoxLayout()
    bottom.setContentsMargins(0, 0, 0, 0)
    bottom.setSpacing(7)

    progress_wrap = QFrame()
    progress_wrap.setObjectName("progress_wrap")
    progress_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    progress_wrap.setFixedHeight(38)
    progress_wrap.setStyleSheet(
        f"QFrame#progress_wrap {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; }}"
    )
    pw_lo = QHBoxLayout(progress_wrap)
    pw_lo.setContentsMargins(10, 5, 10, 5)
    pw_lo.setSpacing(8)
    self.progress_bar = QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setTextVisible(False)
    self.progress_bar.setFixedHeight(16)
    self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.progress_bar.setStyleSheet(
        f"QProgressBar {{ background-color: {C['lane']}; border: none; border-radius: 7px; }}"
        f"QProgressBar::chunk {{ background-color: {C['accent']}; border-radius: 7px; }}"
    )
    pw_lo.addWidget(self.progress_bar, stretch=1)
    self.progress_label = QLabel("0%")
    self.progress_label.setStyleSheet(
        f"color: {C['accent']}; font-size: 13px; font-weight: 900; min-width: 40px;"
    )
    pw_lo.addWidget(self.progress_label)
    bottom.addWidget(progress_wrap, stretch=1)

    self._stat_actions_w, self._stat_actions = self._make_stat_chip("bolt", "Played", "0", C["success"], "Actions played this run")
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
