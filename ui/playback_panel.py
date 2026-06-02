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
    panel.setFixedHeight(106)
    panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    lo = QVBoxLayout(panel)
    lo.setContentsMargins(8, 0, 8, 7)
    lo.setSpacing(0)

    dock = QFrame()
    dock.setObjectName("mf2_playback_dock")
    dock.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    dock.setStyleSheet(
        f"QFrame#mf2_playback_dock {{ background-color: {C['bg_card']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; }}"
    )

    dlo = QVBoxLayout(dock)
    dlo.setContentsMargins(8, 6, 8, 6)
    dlo.setSpacing(4)

    controls_row = QHBoxLayout()
    controls_row.setContentsMargins(0, 0, 0, 0)
    controls_row.setSpacing(6)

    def section_title(txt):
        lbl = QLabel(txt)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 8px; font-weight: 950; "
            "letter-spacing: 0.75px; background: transparent;"
        )
        return lbl

    def mini_label(txt):
        lbl = QLabel(txt)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 8px; font-weight: 900; "
            "background: transparent;"
        )
        return lbl

    def vline():
        line = QFrame()
        line.setFixedSize(1, 40)
        line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        line.setStyleSheet(f"background-color: {C['border']}; border: none;")
        return line

    # ── 1. Playback buttons ────────────────────────────
    play_section = QFrame()
    play_section.setFixedWidth(134)
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
    self.start_btn.setIcon(icon("play", 13, C["text"]))
    self.start_btn.setIconSize(QSize(13, 13))
    self.start_btn.setToolTip("Start playback (F9)")
    self.start_btn.setFixedSize(58, 36)
    self.start_btn.setStyleSheet(
        f"QPushButton#play_btn {{ background-color: #063c1f; color: {C['text']}; "
        f"border: 1px solid {C['success']}; border-radius: 7px; font-size: 10px; font-weight: 950; padding: 0 6px; }}"
        f"QPushButton#play_btn:hover {{ background-color: #07562b; border-color: {C['success']}; }}"
    )
    self.start_btn.clicked.connect(self.start)
    play_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton()
    self.pause_btn.setObjectName("pause_btn")
    self.pause_btn.setIcon(icon("play", 13, C["text_dim"]))
    self.pause_btn.setIconSize(QSize(13, 13))
    self.pause_btn.setToolTip("Pause / resume playback (Esc)")
    self.pause_btn.setFixedSize(34, 36)
    self.pause_btn.setStyleSheet(
        f"QPushButton#pause_btn {{ background-color: {C['bg_tertiary']}; color: {C['pause_cyan']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 0; }}"
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
    self.stop_btn.setFixedSize(34, 36)
    self.stop_btn.setStyleSheet(
        f"QPushButton#stop_btn {{ background-color: {C['bg_tertiary']}; color: {C['error']}; "
        f"border: 1px solid {C['border_light']}; border-radius: 7px; padding: 0; }}"
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
    options_section.setFixedWidth(254)
    options_section.setStyleSheet("background: transparent; border: none;")
    opt_lo = QVBoxLayout(options_section)
    opt_lo.setContentsMargins(0, 0, 0, 0)
    opt_lo.setSpacing(4)
    opt_lo.addWidget(section_title("OPTIONS"))

    row_one = QHBoxLayout()
    row_one.setContentsMargins(0, 0, 0, 0)
    row_one.setSpacing(5)

    speed_box = QVBoxLayout()
    speed_box.setContentsMargins(0, 0, 0, 0)
    speed_box.setSpacing(2)
    speed_box.addWidget(mini_label("Speed"))
    self.speed_combo = QComboBox()
    self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "3.0x"])
    self.speed_combo.setCurrentIndex(3)
    self.speed_combo.currentTextChanged.connect(self._on_speed_change)
    self.speed_combo.setFixedSize(66, 24)
    speed_box.addWidget(self.speed_combo)
    row_one.addLayout(speed_box)

    loops_box = QVBoxLayout()
    loops_box.setContentsMargins(0, 0, 0, 0)
    loops_box.setSpacing(2)
    loops_box.addWidget(mini_label("Loops"))
    loop_pair = QFrame()
    loop_pair.setStyleSheet("background: transparent; border: none;")
    loop_pair_lo = QHBoxLayout(loop_pair)
    loop_pair_lo.setContentsMargins(0, 0, 0, 0)
    loop_pair_lo.setSpacing(3)
    self.loops_spin = QSpinBox()
    self.loops_spin.setRange(1, 9999)
    self.loops_spin.setValue(1)
    self.loops_spin.setFixedSize(30, 24)
    loop_pair_lo.addWidget(self.loops_spin)
    self.inf_check = QCheckBox("∞")
    self.inf_check.setObjectName("pill_check")
    self.inf_check.setToolTip("Infinite loop")
    self.inf_check.setFixedSize(22, 24)
    loop_pair_lo.addWidget(self.inf_check)
    loops_box.addWidget(loop_pair)
    row_one.addLayout(loops_box)
    self.sim_check = QCheckBox("Sim")
    self.sim_check.setObjectName("pill_check")
    self.sim_check.setToolTip("Simulation mode")
    self.sim_check.setFixedSize(36, 23)
    row_one.addWidget(self.sim_check, alignment=Qt.AlignmentFlag.AlignBottom)

    self.human_check = QCheckBox("Hum")
    self.human_check.setObjectName("pill_check")
    self.human_check.setToolTip("Humanized movement curve")
    self.human_check.setFixedSize(38, 23)
    self.human_check.setChecked(True)
    row_one.addWidget(self.human_check, alignment=Qt.AlignmentFlag.AlignBottom)

    self.focus_check = QCheckBox("Lock")
    self.focus_check.setObjectName("pill_check")
    self.focus_check.setToolTip("Keep playback targeted to the captured window")
    self.focus_check.setFixedSize(40, 23)
    row_one.addWidget(self.focus_check, alignment=Qt.AlignmentFlag.AlignBottom)
    row_one.addStretch()

    opt_lo.addLayout(row_one)
    opt_lo.addStretch()
    controls_row.addWidget(options_section)
    controls_row.addStretch()
    self.collapse_playback_btn = QPushButton("Collapse")
    self.collapse_playback_btn.setToolTip("Collapse playback panel")
    self.collapse_playback_btn.setFixedSize(58, 24)
    self.collapse_playback_btn.clicked.connect(lambda: self._set_playback_collapsed(True))
    controls_row.addWidget(self.collapse_playback_btn, alignment=Qt.AlignmentFlag.AlignTop)
    dlo.addLayout(controls_row)

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
    progress_wrap.setFixedHeight(32)
    pw_lo = QHBoxLayout(progress_wrap)
    pw_lo.setContentsMargins(8, 6, 8, 6)
    pw_lo.setSpacing(7)

    self.progress_bar = QProgressBar()
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setTextVisible(False)
    self.progress_bar.setFixedHeight(11)
    self.progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.progress_bar.setStyleSheet(
        f"QProgressBar {{ background-color: {C['lane']}; border: none; border-radius: 5px; }}"
        f"QProgressBar::chunk {{ background-color: {C['accent']}; border-radius: 5px; }}"
    )
    pw_lo.addWidget(self.progress_bar, stretch=1)

    self.progress_label = QLabel("0%")
    self.progress_label.setStyleSheet(
        f"color: {C['accent']}; font-size: 10px; font-weight: 950; "
        "min-width: 34px; background: transparent;"
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
    stats_row.addStretch()
    progress_row.addLayout(stats_row)
    dlo.addLayout(progress_row)
    lo.addWidget(dock, stretch=1)
    self.playback_dock = dock

    self.playback_restore_btn = QPushButton("Show playback panel")
    self.playback_restore_btn.setToolTip("Restore playback controls")
    self.playback_restore_btn.setFixedHeight(24)
    self.playback_restore_btn.clicked.connect(lambda: self._set_playback_collapsed(False))
    self.playback_restore_btn.setVisible(False)
    lo.addWidget(self.playback_restore_btn)
    return panel
