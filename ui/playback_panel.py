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
    """Bottom panel: fixed controls/options, expanding progress bar, static stats."""
    C = COLORS
    panel = QFrame()
    panel.setObjectName("mf2_playback_panel")
    panel.setStyleSheet(f"QFrame#mf2_playback_panel {{ background-color: {C['bg']}; border: none; }}")
    panel.setFixedHeight(188)
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    lo = QVBoxLayout(panel)
    lo.setContentsMargins(8, 2, 8, 8)
    lo.setSpacing(0)

    dock = QFrame()
    dock.setObjectName("mf2_playback_dock")
    dock.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    dock.setStyleSheet(
        f"QFrame#mf2_playback_dock {{ background-color: {C['bg_card']}; "
            f"border: 1px solid {C['border_light']}; border-radius: 8px; }}"
    )

    dlo = QVBoxLayout(dock)
    dlo.setContentsMargins(10, 9, 10, 9)
    dlo.setSpacing(9)

    controls_row = QHBoxLayout()
    controls_row.setContentsMargins(0, 0, 0, 0)
    controls_row.setSpacing(6)

    def section_title(txt):
        lbl = QLabel(txt)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; "
            "letter-spacing: 0.55px; background: transparent;"
        )
        return lbl

    def mini_label(txt):
        lbl = QLabel(txt)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 11px; "
            "background: transparent;"
        )
        return lbl

    def vline():
        line = QFrame()
        line.setFixedSize(1, 72)
        line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        line.setStyleSheet(f"background-color: {C['border']}; border: none;")
        return line

    # ── 1. Playback buttons ────────────────────────────
    play_section = QFrame()
    play_section.setFixedWidth(166)
    play_section.setStyleSheet("background: transparent; border: none;")
    play_lo = QVBoxLayout(play_section)
    play_lo.setContentsMargins(0, 0, 0, 0)
    play_lo.setSpacing(4)
    play_lo.addWidget(section_title("PLAYBACK"))

    play_row = QHBoxLayout()
    play_row.setContentsMargins(0, 0, 0, 0)
    play_row.setSpacing(5)

    self.start_btn = QPushButton("Start")
    self.start_btn.setObjectName("play_btn")
    self.start_btn.setIcon(icon("play", 14, C["text"]))
    self.start_btn.setIconSize(QSize(14, 14))
    self.start_btn.setToolTip("Start playback (F9)")
    self.start_btn.setFixedSize(70, 40)
    self.start_btn.setStyleSheet(
        f"QPushButton#play_btn {{ background-color: #063c1f; color: {C['text']}; "
        f"border: 1px solid {C['success']}; border-radius: 8px; font-size: 12px; padding: 0 7px; }}"
        f"QPushButton#play_btn:hover {{ background-color: #07562b; border-color: {C['success']}; }}"
    )
    self.start_btn.clicked.connect(self.start)
    play_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton()
    self.pause_btn.setObjectName("pause_btn")
    self.pause_btn.setIcon(icon("play", 13, C["text_dim"]))
    self.pause_btn.setIconSize(QSize(13, 13))
    self.pause_btn.setToolTip("Pause / resume playback (Esc)")
    self.pause_btn.setFixedSize(40, 40)
    self.pause_btn.setStyleSheet(
        f"QPushButton#pause_btn {{ background-color: {C['bg_tertiary']}; color: {C['pause_cyan']}; "
            f"border: 1px solid {C['border_light']}; border-radius: 8px; padding: 0; }}"
        f"QPushButton#pause_btn:hover {{ border-color: {C['pause_cyan']}; }}"
        f"QPushButton#pause_btn:disabled {{ color: {C['text_dark']}; border-color: {C['border']}; }}"
    )
    self.pause_btn.setEnabled(False)
    self.pause_btn.clicked.connect(self.engine.toggle_pause)
    play_row.addWidget(self.pause_btn)

    self.stop_btn = QPushButton()
    self.stop_btn.setObjectName("stop_btn")
    self.stop_btn.setIcon(icon("stop", 12, C["error"]))
    self.stop_btn.setIconSize(QSize(12, 12))
    self.stop_btn.setToolTip("Stop playback")
    self.stop_btn.setFixedSize(40, 40)
    self.stop_btn.setStyleSheet(
        f"QPushButton#stop_btn {{ background-color: {C['bg_tertiary']}; color: {C['error']}; "
            f"border: 1px solid {C['border_light']}; border-radius: 8px; padding: 0; }}"
        f"QPushButton#stop_btn:hover {{ border-color: {C['error']}; }}"
        f"QPushButton#stop_btn:disabled {{ color: {C['text_dark']}; border-color: {C['border']}; }}"
    )
    self.stop_btn.setEnabled(False)
    self.stop_btn.clicked.connect(self.stop)
    play_row.addWidget(self.stop_btn)

    play_lo.addLayout(play_row)

    play_lo.addStretch()
    controls_row.addWidget(play_section)
    controls_row.addWidget(vline(), alignment=Qt.AlignmentFlag.AlignVCenter)

    # ── 2. Playback options ────────────────────────────
    options_section = QFrame()
    options_section.setFixedWidth(280)
    options_section.setStyleSheet("background: transparent; border: none;")
    opt_lo = QVBoxLayout(options_section)
    opt_lo.setContentsMargins(0, 0, 0, 0)
    opt_lo.setSpacing(5)
    opt_lo.addWidget(section_title("OPTIONS"))

    speed_loop_row = QHBoxLayout()
    speed_loop_row.setContentsMargins(0, 0, 0, 0)
    speed_loop_row.setSpacing(10)

    speed_box = QVBoxLayout()
    speed_box.setContentsMargins(0, 0, 0, 0)
    speed_box.setSpacing(2)
    speed_box.addWidget(mini_label("Speed"))
    self.speed_combo = QComboBox()
    self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "3.0x"])
    self.speed_combo.setCurrentIndex(3)
    self.speed_combo.currentTextChanged.connect(self._on_speed_change)
    self.speed_combo.setFixedSize(100, 34)
    self.speed_combo.setStyleSheet(
        f"QComboBox {{ font-size: 13px; padding: 4px 10px; border-radius: 8px; }}"
        f"QComboBox::drop-down {{ width: 20px; border: none; }}"
    )
    speed_box.addWidget(self.speed_combo)
    speed_loop_row.addLayout(speed_box)

    loops_box = QVBoxLayout()
    loops_box.setContentsMargins(0, 0, 0, 0)
    loops_box.setSpacing(2)
    loops_box.addWidget(mini_label("Loops"))
    loop_pair = QFrame()
    loop_pair.setStyleSheet("background: transparent; border: none;")
    loop_pair_lo = QHBoxLayout(loop_pair)
    loop_pair_lo.setContentsMargins(0, 0, 0, 0)
    loop_pair_lo.setSpacing(4)
    self.loops_spin = QSpinBox()
    self.loops_spin.setRange(1, 9999)
    self.loops_spin.setValue(1)
    self.loops_spin.setFixedSize(70, 34)
    self.loops_spin.setStyleSheet("QSpinBox { font-size: 13px; padding: 4px 8px; border-radius: 8px; }")
    loop_pair_lo.addWidget(self.loops_spin)
    self.inf_check = QCheckBox("∞")
    self.inf_check.setObjectName("pill_check")
    self.inf_check.setToolTip("Infinite loop")
    self.inf_check.setFixedSize(40, 34)
    loop_pair_lo.addWidget(self.inf_check)
    loops_box.addWidget(loop_pair)
    speed_loop_row.addLayout(loops_box)
    speed_loop_row.addStretch()
    opt_lo.addLayout(speed_loop_row)

    mode_row = QHBoxLayout()
    mode_row.setContentsMargins(0, 0, 0, 0)
    mode_row.setSpacing(6)
    self.sim_check = QCheckBox("Sim")
    self.sim_check.setObjectName("pill_check")
    self.sim_check.setToolTip("Simulation mode")
    self.sim_check.setFixedSize(54, 30)
    mode_row.addWidget(self.sim_check)

    self.human_check = QCheckBox("Human")
    self.human_check.setObjectName("pill_check")
    self.human_check.setToolTip("Humanized movement curve")
    self.human_check.setFixedSize(76, 30)
    self.human_check.setChecked(True)
    mode_row.addWidget(self.human_check)

    self.focus_check = QCheckBox("Lock")
    self.focus_check.setObjectName("pill_check")
    self.focus_check.setToolTip("Keep playback targeted to the captured window")
    self.focus_check.setFixedSize(64, 30)
    mode_row.addWidget(self.focus_check)
    mode_row.addStretch()
    opt_lo.addLayout(mode_row)
    controls_row.addWidget(options_section)
    controls_row.addStretch()
    self.collapse_playback_btn = QPushButton("Hide")
    self.collapse_playback_btn.setToolTip("Collapse playback panel")
    self.collapse_playback_btn.setFixedSize(46, 28)
    self.collapse_playback_btn.setStyleSheet(
        f"QPushButton {{ color: {C['text']}; font-size: 11px; "
        f"background-color: {C['bg_tertiary']}; border: 1px solid {C['border_light']}; border-radius: 12px; padding: 0 10px; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
    )
    self.collapse_playback_btn.clicked.connect(lambda: self._set_playback_collapsed(True))
    controls_row.addWidget(self.collapse_playback_btn, alignment=Qt.AlignmentFlag.AlignTop)
    dlo.addLayout(controls_row)

    self.playback_feedback_label = QLabel("Timeline feedback will appear here")
    self.playback_feedback_label.setObjectName("playback_feedback")
    self.playback_feedback_label.setFixedHeight(28)
    self.playback_feedback_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.playback_feedback_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.playback_feedback_label.setToolTip("Live playback timeline feedback")
    self.playback_feedback_label.setStyleSheet(
        f"QLabel#playback_feedback {{ background-color: {C['bg_tertiary']}; color: {C['text_dim']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 10px; font-size: 12px; }}"
    )
    dlo.addWidget(self.playback_feedback_label)

    # ── 3. Progress expands; stat chips remain static ───
    progress_row = QHBoxLayout()
    progress_row.setContentsMargins(0, 0, 0, 0)
    progress_row.setSpacing(6)

    progress_wrap = QFrame()
    progress_wrap.setObjectName("progress_wrap")
    progress_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    progress_wrap.setStyleSheet(
        f"QFrame#progress_wrap {{ background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 6px; }}"
    )
    progress_wrap.setFixedHeight(36)
    pw_lo = QHBoxLayout(progress_wrap)
    pw_lo.setContentsMargins(8, 5, 8, 5)
    pw_lo.setSpacing(7)

    self.progress_bar = QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setTextVisible(False)
    self.progress_bar.setFixedHeight(16)
    self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.progress_bar.setStyleSheet(
        f"QProgressBar {{ background-color: {C['lane']}; border: none; border-radius: 5px; }}"
        f"QProgressBar::chunk {{ background-color: {C['accent']}; border-radius: 5px; }}"
    )
    pw_lo.addWidget(self.progress_bar, stretch=1)

    self.progress_label = QLabel("0%")
    self.progress_label.setStyleSheet(
            f"color: {C['accent']}; font-size: 14px; "
            "min-width: 38px; background: transparent;"
    )
    pw_lo.addWidget(self.progress_label)
    progress_row.addWidget(progress_wrap, stretch=1)

    stats_row = QHBoxLayout()
    stats_row.setContentsMargins(0, 0, 0, 0)
    stats_row.setSpacing(5)
    self._stat_actions_w, self._stat_actions = self._make_stat_chip("bolt", "Played", "0", C["success"], "Actions played this run")
    self._stat_loops_w,   self._stat_loops   = self._make_stat_chip("loop", "Loops", "0", C["neon_purple"], "Completed loops")
    self._stat_seq_w,     self._stat_seq     = self._make_stat_chip("delay", "Seq", "44.0s", C["neon_gold"], "Estimated sequence duration")
    self._stat_time_w,    self._stat_time    = self._make_stat_chip("clock", "Time", "0:00:00", C["accent"], "Estimated session time")
    stats_row.addWidget(self._stat_actions_w)
    stats_row.addWidget(self._stat_loops_w)
    stats_row.addWidget(self._stat_seq_w)
    stats_row.addWidget(self._stat_time_w)
    progress_row.addLayout(stats_row)
    dlo.addLayout(progress_row)
    lo.addWidget(dock, stretch=1)
    self.playback_dock = dock

    self.playback_restore_btn = QPushButton("Show playback panel")
    self.playback_restore_btn.setToolTip("Restore playback controls")
    self.playback_restore_btn.setFixedHeight(30)
    self.playback_restore_btn.clicked.connect(lambda: self._set_playback_collapsed(False))
    self.playback_restore_btn.setVisible(False)
    lo.addWidget(self.playback_restore_btn)
    return panel
