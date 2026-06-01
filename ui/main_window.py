"""MacroForge Main Window — fresh modern PyQt6 rebuild.

Layout matches v1.1.0 Tkinter exactly:
- 780x760 default, min 640x560
- Profile tab bar across top
- Left sidebar: Add Action, Playback, Recorder
- Timeline + Inspector inline + Playback dock + Status bar
"""
import os
import sys
import time
import math
import json
import csv
import queue
import ctypes
import threading
from copy import deepcopy
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QCheckBox,
    QProgressBar, QFrame, QMenu,
    QSpinBox, QDoubleSpinBox,
    QFileDialog, QMessageBox, QInputDialog,
    QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QAction, QKeySequence, QShortcut, QIcon

from engine import ExecutionEngine
from models import Action, ProfileManager, SettingsManager
from updater import check_update, perform_update, get_last_update_error
from version import VERSION
from hotkeys import start_hotkeys, stop_hotkeys
from debugger import logger, DebugViewer, get_log_path
from ui.theme import build_stylesheet, COLORS
from ui.timeline import TimelineView
from ui.icons import icon


class StatusDot(QWidget):
    """Animated glowing status indicator."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(COLORS["text_dark"])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._pulse)
        self._pulse_phase = 0.0
        self._glow = False

    def set_color(self, color_hex, glow=False):
        self._color = QColor(color_hex)
        self._glow = glow
        if glow and not self._timer.isActive():
            self._timer.start(50)
        elif not glow and self._timer.isActive():
            self._timer.stop()
            self._pulse_phase = 0.0
        self.update()

    def _pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.15) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = int(self.width() / 2), int(self.height() / 2)
        r = 4
        if self._glow:
            glow_r = int(5 + math.sin(self._pulse_phase) * 2)
            p.setBrush(QBrush(QColor(f"{self._color.name()}30")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)


class MainWindow(QMainWindow):
    """Modern MacroForge main window."""

    _update_found = pyqtSignal(dict)
    _update_not_found = pyqtSignal()
    _update_error = pyqtSignal(str)
    _download_progress = pyqtSignal(int, str)  # pct, info_text
    _do_exit = pyqtSignal()
    _close_update_dlg = pyqtSignal()

    # Engine -> main thread signals
    _play_action = pyqtSignal(int, float)     # idx, dur
    _pause_state = pyqtSignal(bool)
    _complete = pyqtSignal()
    _progress = pyqtSignal(int)
    _status_msg = pyqtSignal(str)

    def __init__(self, profile_manager=None, settings_manager=None):
        super().__init__()
        self.setWindowTitle("MacroForge")
        self.setMinimumSize(640, 560)
        self.resize(780, 760)
        self.setStyleSheet(build_stylesheet())

        # Window / taskbar icon
        try:
            if getattr(sys, "frozen", False):
                ico = os.path.join(os.path.dirname(sys.executable), "MacroForge.ico")
            else:
                ico = os.path.join(os.path.dirname(__file__), "..", "MacroForge.ico")
            ico = os.path.abspath(ico)
            if os.path.exists(ico):
                self.setWindowIcon(QIcon(ico))
        except Exception:
            pass

        # Backend refs
        self.session_manager = profile_manager or ProfileManager()
        self.settings_manager = settings_manager or SettingsManager(self.session_manager.base_dir)
        self.engine = ExecutionEngine(
            self._status_cb,
            self._play_cb,
            self._complete_cb,
            self._progress_cb
        )
        self.engine.pause_cb = self._pause_cb

        # State
        self.active_index = -1
        self.clipboard = None
        self.auto_save_enabled = True
        self._save_session_after = None
        self.history = HistoryManager()
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = None
        self._seq_dur_cache = 0.0

        # Recorder state
        self._recorder = {
            "running": False, "paused": False, "last_time": 0.0,
            "presses": {}, "modifiers": set(), "queue": None,
            "kbd_thread": None, "scroll_thread": None,
            "btn": None, "pause_btn": None, "status_dot": None,
            "status_lbl": None, "time_lbl": None, "actions_lbl": None,
            "overlay": None, "timer_id": None, "poll_id": None,
            "rec_start_time": 0.0,
        }

        # Tray
        self._tray_icon = None

        # Menu ref
        self._action_menu = None
        self._profile_menu = None

        self._build_ui()
        self._setup_shortcuts()
        self._setup_timeline_connections()
        self._setup_hotkeys()
        self._setup_tray()

        # Wire update-check signals for thread-safe UI callbacks
        self._update_found.connect(self._on_update_found)
        self._update_not_found.connect(self._on_update_not_found)
        self._update_error.connect(self._on_update_error)
        self._do_exit.connect(self._real_exit)
        self._close_update_dlg.connect(self._on_close_update_dlg)

        self._play_action.connect(self._do_play_cb)
        self._pause_state.connect(self._do_pause_cb)
        self._complete.connect(self._do_complete_cb)
        self._progress.connect(self._do_progress_cb)
        self._status_msg.connect(self.status)

        self._check_update_silent()
        self.load_last_session()
        self._restore_window_geometry()

    # ═══════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ═══════════════════════════════════════════════════════

    def _hsep(self):
        sep = QFrame()
        sep.setStyleSheet(f"background-color: {COLORS['border']}; min-height: 1px; max-height: 1px;")
        return sep

    def _build_ui(self):
        C = COLORS
        central = QWidget()
        self.setCentralWidget(central)
        main_lo = QHBoxLayout(central)
        main_lo.setContentsMargins(0, 0, 0, 0)
        main_lo.setSpacing(0)

        # ━━ Left sidebar ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        sidebar = QFrame()
        sidebar.setObjectName("glass_card")
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet(f"background-color: {C['bg_secondary']}; border-right: 1px solid {C['border']};")
        sb_lo = QVBoxLayout(sidebar)
        sb_lo.setContentsMargins(10, 10, 10, 10)
        sb_lo.setSpacing(8)

        # Branding + version
        brand_row = QHBoxLayout()
        brand_row.setSpacing(4)
        brand = QLabel("MACROFORGE")
        brand.setObjectName("title")
        brand.setStyleSheet(f"color: {C['accent']}; font-size: 14px; font-weight: 800; letter-spacing: 2px;")
        brand_row.addWidget(brand)
        brand_row.addStretch()
        ver_lbl = QLabel(VERSION)
        ver_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; font-weight: 600;")
        brand_row.addWidget(ver_lbl)
        sb_lo.addLayout(brand_row)

        # ── Add Actions ──
        add_lbl = QLabel("ADD")
        add_lbl.setObjectName("section")
        add_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
        sb_lo.addWidget(add_lbl)
        self._add_btn("Key", self._open_key_dialog, C["key"], sb_lo, "key")
        self._add_btn("Click", self._open_click_dialog, C["click"], sb_lo, "click")
        self._add_btn("Delay", self._open_pause_dialog, C["pause"], sb_lo, "delay")
        self._add_btn("Image", self._open_image_dialog, C["image"], sb_lo, "image")

        sb_lo.addWidget(self._hsep())

        # ── Recorder ──
        rec_lbl = QLabel("REC")
        rec_lbl.setObjectName("section")
        rec_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
        sb_lo.addWidget(rec_lbl)
        rec_card = QFrame()
        rec_card.setObjectName("rec_card")
        rec_card.setStyleSheet(f"QFrame#rec_card {{ background-color: {C['bg_tertiary']}; border-radius: 8px; }}")
        rc_lo = QVBoxLayout(rec_card)
        rc_lo.setContentsMargins(6, 6, 6, 6)
        rc_lo.setSpacing(4)
        rrow = QHBoxLayout()
        self.rec_dot = StatusDot()
        self.rec_dot.set_color(C["text_dark"])
        rrow.addWidget(self.rec_dot)
        self.rec_status = QLabel("IDLE")
        self.rec_status.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 600;")
        rrow.addWidget(self.rec_status)
        rrow.addStretch()
        self.rec_time = QLabel("0:00")
        self.rec_time.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
        rrow.addWidget(self.rec_time)
        self.rec_actions = QLabel("0")
        self.rec_actions.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
        rrow.addWidget(self.rec_actions)
        rc_lo.addLayout(rrow)
        brow = QHBoxLayout()
        self.rec_btn = QPushButton()
        self.rec_btn.setObjectName("icon_btn")
        self.rec_btn.setIcon(icon("record", 16, C["error"]))
        self.rec_btn.setToolTip("Record (F7)")
        self.rec_btn.clicked.connect(self._toggle_record)
        self.rec_pause_btn = QPushButton()
        self.rec_pause_btn.setObjectName("icon_btn")
        self.rec_pause_btn.setIcon(icon("pause", 14, C["accent"]))
        self.rec_pause_btn.setToolTip("Pause")
        self.rec_pause_btn.setEnabled(False)
        self.rec_pause_btn.clicked.connect(self._toggle_record_pause)
        brow.addWidget(self.rec_btn)
        brow.addWidget(self.rec_pause_btn)
        brow.addStretch()
        rc_lo.addLayout(brow)
        sb_lo.addWidget(rec_card)

        self._recorder["btn"] = self.rec_btn
        self._recorder["pause_btn"] = self.rec_pause_btn
        self._recorder["status_dot"] = self.rec_dot
        self._recorder["status_lbl"] = self.rec_status
        self._recorder["time_lbl"] = self.rec_time
        self._recorder["actions_lbl"] = self.rec_actions

        sb_lo.addWidget(self._hsep())

        # ── Playback ──
        play_lbl = QLabel("PLAY")
        play_lbl.setObjectName("section")
        play_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
        sb_lo.addWidget(play_lbl)
        play_card = QFrame()
        play_card.setObjectName("play_card")
        play_card.setStyleSheet(f"QFrame#play_card {{ background-color: {C['bg_tertiary']}; border-radius: 8px; }}")
        pc_lo = QVBoxLayout(play_card)
        pc_lo.setContentsMargins(6, 6, 6, 6)
        pc_lo.setSpacing(5)

        trow = QHBoxLayout()
        trow.setSpacing(6)
        _white = "#ffffff"
        self.start_btn = QPushButton()
        self.start_btn.setObjectName("play_btn")
        self.start_btn.setIcon(icon("play", 16, _white))
        self.start_btn.setIconSize(QSize(16, 16))
        self.start_btn.setToolTip("Start (F9)")
        self.start_btn.setFixedSize(36, 32)
        self.start_btn.clicked.connect(self.start)
        trow.addWidget(self.start_btn)

        self.pause_btn = QPushButton()
        self.pause_btn.setObjectName("pause_btn")
        self.pause_btn.setIcon(icon("pause", 14, _white))
        self.pause_btn.setIconSize(QSize(14, 14))
        self.pause_btn.setToolTip("Pause (Esc)")
        self.pause_btn.setFixedSize(32, 32)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.engine.toggle_pause)
        trow.addWidget(self.pause_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.setIcon(icon("stop", 14, _white))
        self.stop_btn.setIconSize(QSize(14, 14))
        self.stop_btn.setToolTip("Stop")
        self.stop_btn.setFixedSize(32, 32)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        trow.addWidget(self.stop_btn)
        trow.addStretch()
        pc_lo.addLayout(trow)

        srow = QHBoxLayout()
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x", "3.0x"])
        self.speed_combo.setCurrentIndex(3)
        self.speed_combo.currentTextChanged.connect(self._on_speed_change)
        self.speed_combo.setFixedWidth(62)
        srow.addWidget(self.speed_combo)
        self.loops_spin = QSpinBox()
        self.loops_spin.setRange(1, 9999)
        self.loops_spin.setValue(1)
        self.loops_spin.setFixedWidth(48)
        srow.addWidget(self.loops_spin)
        self.inf_check = QCheckBox("\u221e")
        self.inf_check.setToolTip("Infinite loop")
        srow.addWidget(self.inf_check)
        srow.addStretch()
        pc_lo.addLayout(srow)

        crow = QHBoxLayout()
        self.sim_check = QCheckBox("Sim")
        self.sim_check.setToolTip("Simulation mode")
        crow.addWidget(self.sim_check)
        self.human_check = QCheckBox("Hum")
        self.human_check.setToolTip("Human curve")
        self.human_check.setChecked(True)
        crow.addWidget(self.human_check)
        self.focus_check = QCheckBox("Fcs")
        self.focus_check.setToolTip("Focus lock")
        crow.addWidget(self.focus_check)
        crow.addStretch()
        pc_lo.addLayout(crow)
        sb_lo.addWidget(play_card)

        sb_lo.addWidget(self._hsep())

        # ── Inspector ──
        insp_lbl = QLabel("INSPECTOR")
        insp_lbl.setObjectName("section")
        insp_lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
        sb_lo.addWidget(insp_lbl)
        insp_card = QFrame()
        insp_card.setObjectName("insp_card")
        insp_card.setStyleSheet(f"QFrame#insp_card {{ background-color: {C['bg_tertiary']}; border-radius: 8px; }}")
        icard_lo = QVBoxLayout(insp_card)
        icard_lo.setContentsMargins(6, 6, 6, 6)
        icard_lo.setSpacing(4)

        # Toolbar
        ibrow = QHBoxLayout()
        ibrow.setSpacing(4)
        for name, slot, tip, clr in [("check", self._apply_inspector, "Apply", C["success"]),
                          ("cross", self._cancel_inspector, "Cancel", C["error"]),
                          ("trash", lambda: self.delete_action(self.active_index), "Delete", C["error"]),
                          ("duplicate", self._duplicate_inspector, "Duplicate", C["accent"]),
                          ("edit", self._open_active_dialog, "Edit", C["accent"])]:
            b = QPushButton()
            b.setObjectName("icon_btn")
            b.setIcon(icon(name, 14, clr))
            b.setToolTip(tip)
            b.setFixedSize(28, 28)
            if slot:
                b.clicked.connect(slot)
            ibrow.addWidget(b)
        ibrow.addStretch()
        icard_lo.addLayout(ibrow)

        # Empty state
        self.insp_empty = QLabel("Select an action to inspect")
        self.insp_empty.setStyleSheet(f"color: {C['text_dark']}; font-size: 11px; font-style: italic; padding: 10px 0;")
        self.insp_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icard_lo.addWidget(self.insp_empty)

        # Inspector forms (vertical in sidebar)
        self._insp_lo = QVBoxLayout()
        self._insp_lo.setSpacing(4)
        self._insp_lo.setContentsMargins(0, 0, 0, 0)

        # Key inspector
        self.insp_key = QWidget()
        ik_lo = QVBoxLayout(self.insp_key)
        ik_lo.setContentsMargins(0, 0, 0, 0)
        ik_lo.setSpacing(3)
        self.ik_key = QLineEdit(); self.ik_key.setPlaceholderText("key")
        self.ik_dur = QLineEdit(); self.ik_dur.setPlaceholderText("duration")
        self.ik_hold = QCheckBox("Hold mode")
        self.ik_repeat = QLineEdit(); self.ik_repeat.setText("1")
        self.ik_label = QLineEdit(); self.ik_label.setPlaceholderText("label")
        ik_lo.addWidget(QLabel("Key"))
        ik_lo.addWidget(self.ik_key)
        ik_lo.addWidget(QLabel("Duration"))
        ik_lo.addWidget(self.ik_dur)
        ik_lo.addWidget(self.ik_hold)
        ik_lo.addWidget(QLabel("Repeat"))
        ik_lo.addWidget(self.ik_repeat)
        ik_lo.addWidget(QLabel("Label"))
        ik_lo.addWidget(self.ik_label)

        # Pause inspector
        self.insp_pause = QWidget()
        ip_lo = QVBoxLayout(self.insp_pause)
        ip_lo.setContentsMargins(0, 0, 0, 0)
        ip_lo.setSpacing(3)
        self.ip_dur = QLineEdit(); self.ip_dur.setPlaceholderText("duration")
        self.ip_label = QLineEdit(); self.ip_label.setPlaceholderText("label")
        ip_lo.addWidget(QLabel("Duration"))
        ip_lo.addWidget(self.ip_dur)
        ip_lo.addWidget(QLabel("Label"))
        ip_lo.addWidget(self.ip_label)

        # Click inspector
        self.insp_click = QWidget()
        ic_lo = QVBoxLayout(self.insp_click)
        ic_lo.setContentsMargins(0, 0, 0, 0)
        ic_lo.setSpacing(3)
        self.ic_x = QLineEdit(); self.ic_x.setPlaceholderText("x")
        self.ic_y = QLineEdit(); self.ic_y.setPlaceholderText("y")
        self.ic_btn = QComboBox()
        self.ic_btn.addItems(["left", "right", "middle"])
        self.ic_rand = QLineEdit(); self.ic_rand.setPlaceholderText("rand")
        self.ic_repeat = QLineEdit(); self.ic_repeat.setText("1")
        self.ic_label = QLineEdit(); self.ic_label.setPlaceholderText("label")
        ic_lo.addWidget(QLabel("X, Y"))
        xy_row = QHBoxLayout()
        xy_row.addWidget(self.ic_x)
        xy_row.addWidget(self.ic_y)
        ic_lo.addLayout(xy_row)
        ic_lo.addWidget(QLabel("Button"))
        ic_lo.addWidget(self.ic_btn)
        ic_lo.addWidget(QLabel("Randomness"))
        ic_lo.addWidget(self.ic_rand)
        ic_lo.addWidget(QLabel("Repeat"))
        ic_lo.addWidget(self.ic_repeat)
        ic_lo.addWidget(QLabel("Label"))
        ic_lo.addWidget(self.ic_label)

        # Image inspector
        self.insp_image = QWidget()
        ii_lo = QVBoxLayout(self.insp_image)
        ii_lo.setContentsMargins(0, 0, 0, 0)
        ii_lo.setSpacing(3)
        self.ii_sim = QLineEdit(); self.ii_sim.setText("0.8")
        self.ii_wait = QLineEdit(); self.ii_wait.setText("10.0")
        ii_lo.addWidget(QLabel("Similarity"))
        ii_lo.addWidget(self.ii_sim)
        ii_lo.addWidget(QLabel("Wait timeout"))
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

        # ── Header / top bar ──
        title = QFrame()
        title.setObjectName("topbar")
        title.setFixedHeight(44)
        title.setStyleSheet(
            f"QFrame#topbar {{ background-color: {C['bg_secondary']}; "
            f"border-bottom: 1px solid {C['border']}; }}"
        )
        tl = QHBoxLayout(title)
        tl.setContentsMargins(12, 6, 12, 6)
        tl.setSpacing(8)

        # Profile switcher (left)
        self.profile_btn = QPushButton("Default")
        self.profile_btn.setObjectName("profile_switcher")
        self.profile_btn.setIcon(icon("folder", 14, C["accent"]))
        self.profile_btn.setIconSize(QSize(14, 14))
        self.profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profile_btn.setToolTip("Switch profile")
        self.profile_btn.setStyleSheet(
            f"QPushButton#profile_switcher {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 9px; padding: 6px 14px; "
            f"font-weight: 700; text-align: left; }} "
            f"QPushButton#profile_switcher:hover {{ border-color: {C['accent']}; color: {C['accent']}; }}"
        )
        self.profile_btn.clicked.connect(self._show_profile_menu)
        tl.addWidget(self.profile_btn)

        tl.addStretch()

        # Status pill (far right)
        status_pill = QFrame()
        status_pill.setObjectName("status_pill")
        status_pill.setStyleSheet(
            f"QFrame#status_pill {{ background-color: {C['bg_tertiary']}; "
            f"border: 1px solid {C['border']}; border-radius: 13px; }}"
        )
        sp_lo = QHBoxLayout(status_pill)
        sp_lo.setContentsMargins(11, 5, 13, 5)
        sp_lo.setSpacing(7)
        self.status_dot = StatusDot()
        self.status_dot.set_color(C["text_dark"])
        sp_lo.addWidget(self.status_dot)
        self.status_text = QLabel("Ready")
        self.status_text.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 600; background: transparent;")
        sp_lo.addWidget(self.status_text)
        tl.addWidget(status_pill)

        up_btn = QPushButton()
        up_btn.setObjectName("icon_btn")
        up_btn.setIcon(icon("update", 16, C["text_dim"]))
        up_btn.setToolTip("Check for updates")
        up_btn.clicked.connect(self._check_update_manual)
        tl.addWidget(up_btn)
        gear = QPushButton()
        gear.setObjectName("icon_btn")
        gear.setIcon(icon("menu", 16, C["text_dim"]))
        gear.setToolTip("Menu")
        gear.clicked.connect(self._show_action_menu)
        tl.addWidget(gear)
        content_lo.addWidget(title)

        # Timeline
        tl_header = QFrame()
        tl_header.setStyleSheet(f"background-color: {C['bg_secondary']}; border-top: 2px solid {C['accent']}; border-bottom: 1px solid {C['border']};")
        tl_hl = QHBoxLayout(tl_header)
        tl_hl.setContentsMargins(10, 4, 10, 4)
        tl_lbl = QLabel("TIMELINE")
        tl_lbl.setStyleSheet(f"color: {C['accent']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        tl_hl.addWidget(tl_lbl)
        hints = QLabel("scroll \u00b7 Ctrl+wheel zoom \u00b7 drag to reorder \u00b7 Del")
        hints.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px;")
        tl_hl.addWidget(hints)
        tl_hl.addStretch()
        self.tl_search = QLineEdit()
        self.tl_search.setPlaceholderText("Search actions…")
        self.tl_search.setClearButtonEnabled(True)
        self.tl_search.setFixedWidth(180)
        self.tl_search.setFixedHeight(24)
        self.tl_search.addAction(icon("search", 14, C["text_dim"]), QLineEdit.ActionPosition.LeadingPosition)
        self.tl_search.setStyleSheet(
            f"QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 12px; padding: 2px 8px; font-size: 11px; }} "
            f"QLineEdit:focus {{ border-color: {C['accent']}; }}"
        )
        self.tl_search.textChanged.connect(lambda t: self.timeline.set_search(t))
        tl_hl.addWidget(self.tl_search)
        content_lo.addWidget(tl_header)

        self.timeline = TimelineView()
        self.timeline.set_actions(self.engine.actions)
        content_lo.addWidget(self.timeline, stretch=1)

        # ── Bottom status bar ──
        status_bar = QFrame()
        status_bar.setObjectName("status_bar")
        status_bar.setStyleSheet(
            f"QFrame#status_bar {{ background-color: {C['bg_secondary']}; "
            f"border-top: 1px solid {C['border']}; }}"
        )
        status_bar.setFixedHeight(36)
        sbar_lo = QHBoxLayout(status_bar)
        sbar_lo.setContentsMargins(12, 5, 12, 5)
        sbar_lo.setSpacing(10)

        # Progress bar (fills remaining width)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {C['border']}; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background-color: {C['accent']}; border-radius: 3px; }}"
        )
        sbar_lo.addWidget(self.progress_bar, stretch=1)
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; min-width: 30px;")
        sbar_lo.addWidget(self.progress_label)
        sbar_lo.addSpacing(16)

        # Icon stats (bolt=actions, loop=loops, delay=seq, clock=time)
        _stat_color = C["text_dim"]
        def _make_stat(icon_name, text="0"):
            f = QFrame()
            f_lo = QHBoxLayout(f)
            f_lo.setContentsMargins(0, 0, 0, 0)
            f_lo.setSpacing(4)
            ico = QLabel()
            ico.setPixmap(icon(icon_name, 12, _stat_color).pixmap(12, 12))
            f_lo.addWidget(ico)
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {_stat_color}; font-size: 11px; background: transparent;")
            f_lo.addWidget(lbl)
            return f, lbl

        self._stat_actions_w, self._stat_actions = _make_stat("bolt", "0")
        self._stat_loops_w,   self._stat_loops   = _make_stat("loop", "0")
        self._stat_seq_w,     self._stat_seq     = _make_stat("delay", "0.0s")
        self._stat_time_w,    self._stat_time    = _make_stat("clock", "0:00:00")

        sbar_lo.addWidget(self._stat_actions_w)
        sbar_lo.addWidget(self._stat_loops_w)
        sbar_lo.addWidget(self._stat_seq_w)
        sbar_lo.addWidget(self._stat_time_w)
        sbar_lo.addStretch()
        content_lo.addWidget(status_bar)

        main_lo.addWidget(content, stretch=1)

    def _add_btn(self, text, callback, color, layout, icon_name="plus"):
        type_map = {"key": "add_key", "click": "add_click", "delay": "add_pause",
                    "image": "add_image", "condition": "add_condition"}
        obj = type_map.get(icon_name, "action_add")
        btn = QPushButton(text)
        btn.setObjectName(obj)
        # Image button has light amber bg → dark icon; others have colored bg → white icon
        icon_color = "#0d0d14" if obj == "add_image" else "#ffffff"
        btn.setIcon(icon(icon_name, 16, icon_color))
        btn.setIconSize(QSize(16, 16))
        btn.setMinimumHeight(40)
        # Compute hover/pressed colors from the base color
        def _shade(hexcol, factor):
            r, g, b = int(hexcol[1:3], 16), int(hexcol[3:5], 16), int(hexcol[5:7], 16)
            r = min(255, int(r * factor))
            g = min(255, int(g * factor))
            b = min(255, int(b * factor))
            return f"#{r:02x}{g:02x}{b:02x}"
        hover = _shade(color, 1.15)
        pressed = _shade(color, 0.85)
        text_col = "#0d0d14" if obj == "add_image" else "#ffffff"
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: {text_col}; border: none; "
            f"border-radius: 4px; padding: 10px 12px; text-align: center; font-size: 12px; font-weight: 700; }}"
            f"QPushButton:hover {{ background-color: {hover}; }}"
            f"QPushButton:pressed {{ background-color: {pressed}; }}"
        )
        btn.clicked.connect(callback)
        layout.addWidget(btn)

    def _label_row(self, text, widget):
        row = QFrame()
        lo = QHBoxLayout(row)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(QLabel(text))
        lo.addWidget(widget)
        return row

    def _show_inspector(self, show=True, action_type="key"):
        for w in (self.insp_key, self.insp_pause, self.insp_click, self.insp_image):
            w.setVisible(False)
        self.insp_empty.setVisible(not show)
        if show:
            mapping = {
                "key": self.insp_key,
                "pause": self.insp_pause,
                "click": self.insp_click,
                "image": self.insp_image,
            }
            mapping.get(action_type, self.insp_key).setVisible(True)

    # ═══════════════════════════════════════════════════════
    #  KEYBOARD SHORTCUTS
    # ═══════════════════════════════════════════════════════

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self.redo)
        QShortcut(QKeySequence("Ctrl+C"), self, self.copy_action)
        QShortcut(QKeySequence("Ctrl+V"), self, self.paste_action)
        QShortcut(QKeySequence("Ctrl+D"), self, self._duplicate_inspector)
        QShortcut(QKeySequence("Delete"), self, self._delete_selected)
        QShortcut(QKeySequence("Ctrl+Delete"), self, self._delete_selected)
        QShortcut(QKeySequence("Escape"), self, self._deselect)
        QShortcut(QKeySequence("Ctrl+S"), self, lambda: (self._do_save_session(), self.status("Session saved")))
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.timeline.setFocus())

    def _deselect(self):
        self.select(-1)
        self.timeline.selected_indices.clear()
        self.timeline.refresh()

    def _delete_selected(self):
        self.delete_action(self.active_index)

    # ═══════════════════════════════════════════════════════
    #  TIMELINE CONNECTIONS
    # ═══════════════════════════════════════════════════════

    def _setup_timeline_connections(self):
        self.timeline.action_clicked.connect(self.select)
        self.timeline.action_double_clicked.connect(self._open_active_dialog)
        self.timeline.action_dragged.connect(self.move_action_to)
        self.timeline.action_context_menu.connect(self._timeline_context_menu)

    def _timeline_context_menu(self, index, pos):
        if index < 0 or index >= len(self.engine.actions):
            return
        self.select(index)
        m = QMenu(self)
        C = COLORS
        m.setStyleSheet(f"""
            QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}
            QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
            QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }}
        """)
        m.addAction("Edit", lambda: self._open_active_dialog(index))
        m.addAction("Duplicate", lambda: self.duplicate_action(index))
        m.addSeparator()
        m.addAction("Move Up", lambda: self.move_action(index, -1))
        m.addAction("Move Down", lambda: self.move_action(index, 1))
        m.addSeparator()
        m.addAction("Delete", lambda: self.delete_action(index))
        m.exec(pos)

    # ═══════════════════════════════════════════════════════
    #  SESSION & PROFILE
    # ═══════════════════════════════════════════════════════

    def load_last_session(self):
        session = self.session_manager.load_profile()
        if session:
            try:
                self.engine.actions = [Action.from_dict(x) for x in session.get("actions", [])]
                settings = session.get("settings", {})
                self.loops_spin.setValue(int(settings.get("loops", 1)))
                self.speed_combo.setCurrentText(f"{float(settings.get('speed', 1.0)):.1f}x")
                self.inf_check.setChecked(settings.get("infinite_loop", False))
                self.human_check.setChecked(settings.get("human_curve", True))
                self.timeline.zoom = settings.get("zoom", 1.0)
                # Window geometry is stored GLOBALLY (see _restore_window_geometry),
                # never per-profile, so switching profiles never moves the window.
                self._invalidate_seq_dur()
                self.active_index = -1
                self.timeline.selected_indices.clear()
                self.timeline.set_active(-1)
                self.timeline.clear_playing()
                self.timeline.set_actions(self.engine.actions)  # sync new list reference
                self.timeline.refresh()
                self.refresh()
                self.actions_played = 0
                self.session_elapsed_time = 0.0
                self.session_start_time = None
                self.update_statistics(immediate=True)
                self.status(f"Profile '{self.session_manager.active}' loaded")
            except Exception:
                if not self.engine.actions:
                    self.status("Failed to load profile")
                else:
                    self.status("Profile partially loaded")
        else:
            self.engine.actions = []
            self.timeline.set_actions(self.engine.actions)
            self.timeline.refresh()
            self.update_statistics(immediate=True)
            self.status("Ready")
        self._refresh_profile_btn()

    def save_session(self):
        if not self.auto_save_enabled:
            return
        if self._save_session_after:
            self._save_session_after.stop()
        self._save_session_after = QTimer.singleShot(500, self._do_save_session)

    def _do_save_session(self):
        settings = {
            "loops": self.loops_spin.value(),
            "speed": float(self.speed_combo.currentText().replace("x", "")),
            "infinite_loop": self.inf_check.isChecked(),
            "human_curve": self.human_check.isChecked(),
            "zoom": self.timeline.zoom,
        }
        self.session_manager.save_profile(self.engine.actions, settings)
        self._save_window_geometry()
        self._save_session_after = None

    def _save_window_geometry(self):
        """Persist window geometry GLOBALLY (independent of profile)."""
        try:
            self.settings_manager.set(
                "window_geometry", self.saveGeometry().toHex().data().decode()
            )
        except Exception:
            pass

    def _restore_window_geometry(self):
        """Restore the last global window geometry, if any."""
        try:
            geo = self.settings_manager.get("window_geometry", "")
            if geo:
                self.restoreGeometry(bytes.fromhex(geo))
        except Exception:
            pass

    def _refresh_profile_btn(self):
        if hasattr(self, "profile_btn"):
            self.profile_btn.setText(f"{self.session_manager.active}  \u25be")

    def _show_profile_menu(self):
        C = COLORS
        m = QMenu(self)
        m.setStyleSheet(
            f"QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }} "
            f"QMenu::item {{ padding: 6px 18px; border-radius: 6px; }} "
            f"QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }} "
            f"QMenu::separator {{ height: 1px; background-color: {C['border']}; margin: 4px 8px; }}"
        )
        active = self.session_manager.active
        for name in self.session_manager.list_profiles():
            label = f"\u2713  {name}" if name == active else f"     {name}"
            act = m.addAction(label)
            act.triggered.connect(lambda checked, n=name: self._switch_profile(n))
        m.addSeparator()
        m.addAction(icon("plus", 14, C["accent"]), "New profile\u2026", self._new_profile_dialog)
        m.addAction(icon("edit", 14, C["accent"]), "Rename\u2026", self._rename_profile_dialog)
        m.addAction(icon("trash", 14, C["error"]), "Delete", self._delete_profile_confirm)
        m.exec(self.profile_btn.mapToGlobal(self.profile_btn.rect().bottomLeft()))

    def _switch_profile(self, name):
        self._do_save_session()
        self.session_manager.switch_profile(name)
        self.load_last_session()
        self._refresh_profile_btn()
        self.status(f"Switched to '{name}'")

    def _new_profile_dialog(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if ok and name.strip():
            name = name.strip()
            self.session_manager.save_profile([], {}, name)
            self._switch_profile(name)

    def _rename_profile_dialog(self):
        old = self.session_manager.active
        name, ok = QInputDialog.getText(self, "Rename Profile", "New name:", text=old)
        if ok and name.strip() and name != old:
            self.session_manager.rename_profile(old, name.strip())
            self._switch_profile(name.strip())

    def _delete_profile_confirm(self):
        name = self.session_manager.active
        reply = QMessageBox.question(self, "Delete Profile",
            f"Delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.session_manager.delete_profile(name)
            profiles = self.session_manager.list_profiles()
            if profiles:
                self._switch_profile(profiles[0])
            else:
                self.session_manager.active = "Default"
                self.engine.actions = []
                self.refresh()

    # ═══════════════════════════════════════════════════════
    #  SELECTION & EDITING
    # ═══════════════════════════════════════════════════════

    def select(self, index):
        if index is None or index < 0 or index >= len(self.engine.actions):
            self.active_index = -1
            self.timeline.set_active(-1)
            self.timeline.selected_indices.clear()
            self._show_inspector(False)
            return
        self.active_index = index
        self.timeline.selected_indices.clear()
        self.timeline.set_active(index)
        action = self.engine.actions[index]
        self._show_inspector(True, action.action_type)
        if action.action_type == "key":
            self.ik_key.setText(action.key)
            self.ik_dur.setText(str(action.duration))
            self.ik_hold.setChecked(action.hold_mode)
            self.ik_repeat.setText(str(getattr(action, 'repeat_count', 1)))
            self.ik_label.setText(getattr(action, 'label', ''))
        elif action.action_type == "pause":
            self.ip_dur.setText(str(action.duration))
            self.ip_label.setText(getattr(action, 'label', ''))
        elif action.action_type == "click":
            self.ic_x.setText(str(getattr(action, 'click_x', 0)))
            self.ic_y.setText(str(getattr(action, 'click_y', 0)))
            self.ic_btn.setCurrentText(getattr(action, 'click_button', 'left'))
            self.ic_rand.setText(str(getattr(action, 'click_rand_radius', 0)))
            self.ic_repeat.setText(str(getattr(action, 'repeat_count', 1)))
            self.ic_label.setText(getattr(action, 'label', ''))
        elif action.action_type == "image":
            self.ii_sim.setText(str(getattr(action, 'similarity', 0.8)))
            self.ii_wait.setText(str(getattr(action, 'wait_timeout', 10.0)))

    def _apply_inspector(self):
        if self.active_index < 0 or self.active_index >= len(self.engine.actions):
            QMessageBox.warning(self, "No Selection", "Please select an action first")
            return
        try:
            action = self.engine.actions[self.active_index]
            self.history.push(self.engine.actions)
            if action.action_type == "key":
                action.key = self.ik_key.text().strip()
                action.duration = float(self.ik_dur.text())
                action.hold_mode = self.ik_hold.isChecked()
                action.repeat_count = max(1, int(self.ik_repeat.text() or 1))
                action.label = self.ik_label.text().strip()
            elif action.action_type == "pause":
                action.duration = float(self.ip_dur.text())
                action.label = self.ip_label.text().strip()
            elif action.action_type == "click":
                action.click_x = int(self.ic_x.text())
                action.click_y = int(self.ic_y.text())
                action.click_button = self.ic_btn.currentText()
                action.click_rand_radius = int(self.ic_rand.text() or 0)
                action.repeat_count = max(1, int(self.ic_repeat.text() or 1))
                action.label = self.ic_label.text().strip()
            elif action.action_type == "image":
                action.similarity = float(self.ii_sim.text())
                action.wait_timeout = float(self.ii_wait.text())
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status("Applied changes")
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Input", f"Invalid value: {e}")

    def _cancel_inspector(self):
        if self.active_index >= 0:
            self.select(self.active_index)
            self.status("Changes cancelled")

    def _open_active_dialog(self, index=None):
        idx = index if index is not None else self.active_index
        if idx < 0 or idx >= len(self.engine.actions):
            return
        action = self.engine.actions[idx]
        if action.action_type == "image":
            self._open_image_editor(idx)
        elif action.action_type == "click":
            self._open_click_editor(idx)
        elif action.action_type == "pause":
            self._open_pause_editor(idx)
        else:
            self._open_key_editor(idx)

    def _duplicate_inspector(self):
        self.duplicate_action(self.active_index)

    # ═══════════════════════════════════════════════════════
    #  ACTION MANAGEMENT
    # ═══════════════════════════════════════════════════════

    def delete_action(self, index):
        selected = self.timeline.selected_indices
        if selected:
            indices = sorted(selected, reverse=True)
            if not indices or indices[0] >= len(self.engine.actions):
                self.timeline.selected_indices.clear()
                return
            self.history.push(self.engine.actions)
            for idx in indices:
                if 0 <= idx < len(self.engine.actions):
                    self.engine.actions.pop(idx)
            self.active_index = -1
            self.timeline.selected_indices.clear()
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status(f"Deleted {len(indices)} actions")
            return
        if index < 0 or index >= len(self.engine.actions):
            return
        self.history.push(self.engine.actions)
        self.engine.actions.pop(index)
        self.active_index = -1
        self.timeline.selected_indices.clear()
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Deleted action")

    def duplicate_action(self, index):
        if index < 0 or index >= len(self.engine.actions):
            self.status("No action selected to duplicate")
            return
        self.history.push(self.engine.actions)
        self.engine.actions.insert(index + 1, deepcopy(self.engine.actions[index]))
        self.active_index = index + 1
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Duplicated action")

    def move_action(self, index, direction):
        if index < 0 or index >= len(self.engine.actions):
            return
        new_index = index + direction
        if new_index < 0 or new_index >= len(self.engine.actions):
            return
        self.history.push(self.engine.actions)
        action = self.engine.actions.pop(index)
        self.engine.actions.insert(new_index, action)
        self.active_index = new_index
        self.refresh()
        self.save_session()
        self.status("Moved action")

    def move_action_to(self, index, target_index):
        if index < 0 or index >= len(self.engine.actions):
            return
        if target_index < 0 or target_index >= len(self.engine.actions):
            return
        self.history.push(self.engine.actions)
        action = self.engine.actions.pop(index)
        self.engine.actions.insert(target_index, action)
        self.active_index = target_index
        self.refresh()
        self.update_statistics(immediate=True)
        self.save_session()
        self.status("Moved action")

    def copy_action(self):
        if self.active_index < 0 or self.active_index >= len(self.engine.actions):
            self.status("No action selected to copy")
            return
        self.clipboard = deepcopy(self.engine.actions[self.active_index])
        self.status("Copied action")

    def paste_action(self):
        if self.clipboard is None:
            self.status("Clipboard empty")
            return
        self.history.push(self.engine.actions)
        new_action = deepcopy(self.clipboard)
        if 0 <= self.active_index < len(self.engine.actions):
            insert_at = self.active_index + 1
        else:
            insert_at = len(self.engine.actions)
        self.engine.actions.insert(insert_at, new_action)
        self.active_index = insert_at
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Pasted action")

    # ═══════════════════════════════════════════════════════
    #  PLAYBACK
    # ═══════════════════════════════════════════════════════

    def _on_speed_change(self, text):
        try:
            self.engine.speed = float(text.replace("x", ""))
        except ValueError:
            pass

    def start(self):
        if self.engine.running:
            self.status("Already running")
            return
        if not self.engine.actions:
            self.status("No actions to play")
            return
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.status_dot.set_color(COLORS["playing"], glow=True)
        self.status_text.setText("Playing")
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.engine.infinite_loop = self.inf_check.isChecked()
        self.engine.simulation_mode = self.sim_check.isChecked()
        self.engine.human_curve = self.human_check.isChecked()
        self.engine.focus_lock = self.focus_check.isChecked()
        self.engine.loops = self.loops_spin.value()
        try:
            self.engine.speed = float(self.speed_combo.currentText().replace("x", ""))
        except ValueError:
            self.engine.speed = 1.0
        self.engine.start()

    def stop(self):
        self.engine.stop()
        self.timeline.clear_playing()
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_dot.set_color(COLORS["text_dark"])
        self.status_text.setText("Ready")
        if self.session_start_time:
            self.session_elapsed_time += time.time() - self.session_start_time
            self.session_start_time = None
        self.update_statistics(immediate=True)

    def _status_cb(self, msg):
        self._status_msg.emit(msg)

    def _play_cb(self, idx, dur):
        self._play_action.emit(idx, dur)

    def _do_play_cb(self, idx, dur):
        self.playing_index = idx
        self.actions_played += 1
        speed = max(self.engine.speed_multiplier, 0.01)
        adjusted_dur = dur / speed
        self.timeline.set_playing(idx, adjusted_dur)
        self.update_statistics()

    def _pause_cb(self, paused):
        self._pause_state.emit(paused)

    def _do_pause_cb(self, paused):
        self.timeline.set_paused(paused)
        if paused:
            self.pause_btn.setIcon(icon("play", 14, COLORS["text_inverse"]))
            self.pause_btn.setToolTip("Resume (Esc)")
            self.status_text.setText("Paused")
        else:
            self.pause_btn.setIcon(icon("pause", 14, COLORS["text_inverse"]))
            self.pause_btn.setToolTip("Pause (Esc)")
            self.status_text.setText("Running")

    def _complete_cb(self):
        self._complete.emit()

    def _do_complete_cb(self):
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.playing_index = -1
        self.timeline.clear_playing()
        self.status_dot.set_color(COLORS["text_dark"])
        self.status_text.setText("Finished")
        if self.session_start_time:
            self.session_elapsed_time += time.time() - self.session_start_time
            self.session_start_time = None
        self.update_statistics(immediate=True)

    def _progress_cb(self, pct):
        self._progress.emit(pct)

    def _do_progress_cb(self, pct):
        self.progress_bar.setValue(int(pct))
        self.progress_label.setText(f"{int(pct)}%")

    # ═══════════════════════════════════════════════════════
    #  RECORDER
    # ═══════════════════════════════════════════════════════

    def _toggle_record(self):
        rec = self._recorder
        if not rec["running"]:
            self._start_recording()
        else:
            self._stop_recording()

    def _toggle_record_pause(self):
        rec = self._recorder
        if not rec["running"]:
            return
        if rec["paused"]:
            rec["paused"] = False
            rec["last_time"] = time.time()
            self.rec_pause_btn.setText(" Pause")
            self.rec_pause_btn.setStyleSheet(f"background: {COLORS['playing']}; color: #fff; border-radius: 8px;")
            self.rec_dot.set_color("#ff4444", glow=True)
            self.rec_status.setText("RECORDING")
            self.rec_status.setStyleSheet(f"color: #ff4444; font-size: 11px; font-weight: 600;")
            self._rec_timer_tick()
            self.status("Recording resumed")
            self._show_rec_badge(True)
        else:
            rec["paused"] = True
            self.rec_pause_btn.setText(" Resume")
            self.rec_dot.set_color("#f0a844", glow=True)
            self.rec_status.setText("PAUSED")
            self.rec_status.setStyleSheet(f"color: #f0a844; font-size: 11px; font-weight: 600;")
            self.status("Recording paused — click Resume to continue, or Stop to finish")
            self._show_rec_badge(False)

    def _show_rec_badge(self, show):
        rec = self._recorder
        if show:
            if rec["overlay"] is not None:
                return
            # We use a simple QWidget overlay positioned near main window
            ov = QFrame()
            ov.setStyleSheet("background-color: transparent; border: none;")
            ov.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            ov.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
            ov.setFixedSize(60, 28)
            lbl = QLabel("REC")
            lbl.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 12px;")
            lo = QHBoxLayout(ov)
            lo.addWidget(lbl)
            ov.show()
            # Position near top-right of main window
            geo = self.geometry()
            ov.move(geo.x() + geo.width() - 72, geo.y() + 10)
            rec["overlay"] = ov
        else:
            if rec["overlay"] is not None:
                rec["overlay"].close()
                rec["overlay"] = None

    def _rec_timer_tick(self):
        rec = self._recorder
        if not rec["running"] or rec["paused"]:
            return
        elapsed = int(time.time() - rec["rec_start_time"])
        mins, secs = divmod(elapsed, 60)
        self.rec_time.setText(f"{mins}:{secs:02d}")
        QTimer.singleShot(1000, self._rec_timer_tick)

    def _update_rec_action_count(self):
        rec = self._recorder
        if rec["running"] and rec["actions_lbl"] is not None:
            rec["actions_lbl"].setText(str(len(self.engine.actions)))

    def _start_recording(self):
        if self._recorder["running"]:
            return
        rec = self._recorder
        rec["running"] = True
        rec["paused"] = False
        rec["last_time"] = time.time()
        rec["presses"].clear()
        rec["modifiers"].clear()
        rec["queue"] = queue.Queue()
        self.rec_btn.setText(" Stop")
        self.rec_btn.setStyleSheet(f"background-color: {COLORS['error']}; color: #fff; border-radius: 8px; padding: 6px 12px; font-weight: 600;")
        self.rec_pause_btn.setText(" Pause")
        self.rec_pause_btn.setEnabled(True)
        self.rec_pause_btn.setStyleSheet(f"background: {COLORS['playing']}; color: #fff; border-radius: 8px;")
        self.rec_dot.set_color("#ff4444", glow=True)
        self.rec_status.setText("RECORDING")
        self.rec_status.setStyleSheet("color: #ff4444; font-size: 11px; font-weight: 600;")
        self.rec_actions.setText("0")
        rec["rec_start_time"] = time.time()
        self._rec_timer_tick()
        self.status("Recording…")
        self._show_rec_badge(True)

        # Cancel stale poll
        if rec["poll_id"]:
            rec["poll_id"].stop()
            rec["poll_id"] = None
        self._poll_queue()

        # Keyboard polling thread
        rec["kbd_thread"] = threading.Thread(target=self._kbd_poll_loop, daemon=True)
        rec["kbd_thread"].start()

        # Scroll hook thread
        rec["scroll_thread"] = threading.Thread(target=self._scroll_hook_loop, daemon=True)
        rec["scroll_thread"].start()
        logger.info("Recording started")

    def _kbd_poll_loop(self):
        user32 = ctypes.windll.user32
        rec = self._recorder
        MODS = {"shift", "ctrl", "alt"}
        vk_name = {}
        for vk in range(0x41, 0x5B):
            vk_name[vk] = chr(vk).lower()
        for vk in range(0x30, 0x3A):
            vk_name[vk] = chr(vk)
        vk_name.update({
            0x08: "backspace", 0x09: "tab", 0x0D: "return",
            0x1B: "esc", 0x20: "space",
            0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
            0x10: "shift", 0x11: "ctrl", 0x12: "alt",
            0x01: "mouse_left", 0x02: "mouse_right", 0x04: "mouse_middle",
        })
        for i in range(0x70, 0x7C):
            vk_name[i] = f"f{i - 0x6F}"
        vks = list(vk_name.keys())
        prev = {}
        while rec["running"]:
            for vk in vks:
                name = vk_name[vk]
                down = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
                was_down = prev.get(vk, False)
                if down and not was_down:
                    rec["presses"][name] = time.time()
                    if name in MODS:
                        rec["modifiers"].add(name)
                elif not down and was_down:
                    if name in MODS:
                        rec["modifiers"].discard(name)
                    if name not in rec["presses"]:
                        prev[vk] = down
                        continue
                    press_time = rec["presses"].pop(name)
                    release_time = time.time()
                    hold_dur = release_time - press_time
                    if hold_dur < 0.05:
                        prev[vk] = down
                        continue
                    if name == "backspace" and not rec["modifiers"]:
                        # Use invokeMethod to run on main thread
                        QTimer.singleShot(0, self._rec_delete_last)
                        prev[vk] = down
                        continue
                    if rec["paused"]:
                        prev[vk] = down
                        continue
                    delay = press_time - rec["last_time"]
                    if delay > 0.05:
                        rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                    if name.startswith("mouse_"):
                        pt = ctypes.wintypes.POINT()
                        user32.GetCursorPos(ctypes.byref(pt))
                        is_hold = hold_dur > 0.3
                        dur = round(hold_dur, 2) if is_hold else 0.05
                        act = Action("[CLICK]", dur, hold_mode=is_hold, action_type="click")
                        act.click_x, act.click_y = pt.x, pt.y
                        act.click_button = name.replace("mouse_", "")
                        act.click_coord_mode = "absolute"
                        rec["queue"].put(act)
                        rec["last_time"] = release_time
                    else:
                        active_mods = rec["modifiers"] - {name}
                        if active_mods and name not in MODS:
                            combo = "+".join(sorted(active_mods)) + "+" + name
                            rec["queue"].put(Action(combo, 0.05, action_type="key"))
                        else:
                            is_hold = hold_dur > 0.3
                            if is_hold:
                                rec["queue"].put(Action(name, round(hold_dur, 2), hold_mode=True, action_type="key"))
                            else:
                                rec["queue"].put(Action(name, 0.05, action_type="key"))
                        rec["last_time"] = release_time
                prev[vk] = down
            time.sleep(1 / 60)

    def _rec_delete_last(self):
        try:
            if self.engine.actions:
                self.history.push(self.engine.actions)
                self.engine.actions.pop()
                self.active_index = len(self.engine.actions) - 1
                self.refresh()
                self.update_statistics()
                self.save_session()
                self._update_rec_action_count()
                self.status("Deleted last recorded action")
        except Exception as e:
            logger.debug(f"rec_delete_last: {e}")

    def _scroll_hook_loop(self):
        user32 = ctypes.windll.user32
        rec = self._recorder
        WH_MOUSE_LL = 14
        WM_MOUSEWHEEL = 0x020A
        WM_MOUSEHWHEEL = 0x020E
        PM_REMOVE = 0x0001
        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", ctypes.wintypes.POINT),
                ("mouseData", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32),
                ("dwExtraInfo", ctypes.c_uint64),
            ]
        @ctypes.WINFUNCTYPE(ctypes.c_int64, ctypes.c_int32, ctypes.c_uint64, ctypes.c_int64)
        def hook_proc(nCode, wParam, lParam):
            if nCode >= 0 and rec["running"] and not rec["paused"]:
                if wParam == WM_MOUSEWHEEL or wParam == WM_MOUSEHWHEEL:
                    try:
                        if rec["queue"] is None:
                            return user32.CallNextHookEx(None, nCode, wParam, lParam)
                        data = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                        delta = ctypes.c_int16(data.mouseData >> 16).value
                        direction = "scroll_up" if delta > 0 else "scroll_down"
                        now = time.time()
                        delay = now - rec["last_time"]
                        if delay > 0.05:
                            rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                        rec["queue"].put(Action(f"[{direction.upper()}]", 0.05, action_type="key"))
                        rec["last_time"] = now
                        self.status(f"Recorded: {direction}")
                    except Exception as e:
                        logger.debug(f"scroll hook: {e}")
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
        hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, hook_proc, None, 0)
        if not hook_id:
            logger.error("Failed to install scroll hook")
            return
        logger.info("Scroll hook installed")
        msg = ctypes.wintypes.MSG()
        while rec["running"]:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)
        user32.UnhookWindowsHookEx(hook_id)
        logger.info("Scroll hook removed")

    def _poll_queue(self):
        rec = self._recorder
        try:
            if not rec["running"] and (rec["queue"] is None or rec["queue"].empty()):
                rec["poll_id"] = None
                return
            updated = False
            while rec["queue"] is not None and not rec["queue"].empty():
                try:
                    action = rec["queue"].get_nowait()
                except queue.Empty:
                    break
                self.history.push(self.engine.actions)
                self.engine.actions.append(action)
                self._update_rec_action_count()
                updated = True
            if updated:
                self.active_index = len(self.engine.actions) - 1
                self.refresh()
                self.timeline.ensure_visible(self.active_index)
                self.update_statistics()
                self.save_session()
        except Exception as e:
            logger.error(f"_poll_queue: {e}")
        if rec["running"]:
            rec["poll_id"] = QTimer.singleShot(50, self._poll_queue)

    def _stop_recording(self):
        if not self._recorder["running"]:
            return
        rec = self._recorder
        rec["running"] = False
        rec["paused"] = False
        if rec.get("kbd_thread") and rec["kbd_thread"].is_alive():
            rec["kbd_thread"].join(timeout=0.05)
        if rec.get("scroll_thread") and rec["scroll_thread"].is_alive():
            rec["scroll_thread"].join(timeout=0.2)
        self._show_rec_badge(False)
        self.rec_btn.setText("")
        self.rec_btn.setStyleSheet("")
        self.rec_pause_btn.setText("")
        self.rec_pause_btn.setEnabled(False)
        self.rec_pause_btn.setStyleSheet("")
        self.rec_dot.set_color(COLORS["text_dark"])
        self.rec_status.setText("IDLE")
        self.rec_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; font-weight: 600;")
        self.rec_time.setText("0:00")
        self.rec_actions.setText("0")
        if rec["timer_id"]:
            rec["timer_id"].stop()
            rec["timer_id"] = None
        try:
            if rec["queue"] is not None:
                now = time.time()
                for k, t in list(rec["presses"].items()):
                    hold = now - t
                    delay = t - rec["last_time"]
                    if delay > 0.05:
                        rec["queue"].put(Action("[DELAY]", round(delay, 2), action_type="pause"))
                    if k.startswith("mouse_"):
                        pt = ctypes.wintypes.POINT()
                        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                        act = Action("[CLICK]", 0.05, action_type="click")
                        act.click_x, act.click_y = pt.x, pt.y
                        act.click_button = k.replace("mouse_", "")
                        act.click_coord_mode = "absolute"
                        rec["queue"].put(act)
                    else:
                        rec["queue"].put(Action(k, round(hold, 2), hold_mode=True, action_type="key"))
                    rec["last_time"] = now
            rec["presses"].clear()
            rec["modifiers"].clear()
        except Exception as e:
            logger.error(f"rec flush: {e}")
        if rec["poll_id"]:
            try:
                rec["poll_id"].stop()
            except Exception as e:
                logger.debug(f"after_cancel: {e}")
            rec["poll_id"] = None
        self._poll_queue_final()
        rec["kbd_thread"] = None
        rec["scroll_thread"] = None
        rec["queue"] = None
        self.status("Recording stopped")

    def _poll_queue_final(self):
        rec = self._recorder
        try:
            updated = False
            while rec["queue"] is not None and not rec["queue"].empty():
                try:
                    action = rec["queue"].get_nowait()
                except queue.Empty:
                    break
                self.history.push(self.engine.actions)
                self.engine.actions.append(action)
                updated = True
            if updated:
                self.active_index = len(self.engine.actions) - 1
                self.refresh()
                self.update_statistics()
                self.save_session()
        except Exception as e:
            logger.error(f"_poll_queue_final: {e}")

    # ═══════════════════════════════════════════════════════
    #  MENU SYSTEM
    # ═══════════════════════════════════════════════════════

    def _show_action_menu(self):
        m = QMenu(self)
        C = COLORS
        m.setStyleSheet(f"""
            QMenu {{ background-color: {C['bg_tertiary']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}
            QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
            QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }}
            QMenu::separator {{ height: 1px; background-color: {C['border']}; margin: 4px 8px; }}
        """)
        active = self.session_manager.active
        profiles_menu = QMenu("Profiles", self)
        profiles_menu.setStyleSheet(m.styleSheet())
        for name in self.session_manager.list_profiles():
            a = QAction(f"  {'>' if name == active else ' '}  {name}", self)
            a.triggered.connect(lambda checked, n=name: self._switch_profile(n))
            profiles_menu.addAction(a)
        profiles_menu.addSeparator()
        profiles_menu.addAction("New profile…", self._new_profile_dialog)
        profiles_menu.addAction("Rename…", self._rename_profile_dialog)
        profiles_menu.addAction("Delete", self._delete_profile_confirm)
        m.addMenu(profiles_menu)
        m.addSeparator()
        m.addAction("Save     Ctrl+S", lambda: (self._do_save_session(), self.status(f"Profile '{self.session_manager.active}' saved")))
        m.addAction("Export JSON…", self.save)
        m.addAction("Import JSON…", self.load)
        m.addAction("Export CSV…", self.export_csv)
        m.addAction("Import CSV…", self.import_csv)
        m.addSeparator()
        m.addAction("Reset statistics", self.reset_stats)
        m.addAction("Clear all actions", self.clear_all)
        m.addSeparator()
        m.addAction("Settings", self.open_settings_dialog)
        m.addAction("Debug log", self.open_debug_viewer)
        m.addAction("Check for Updates", self._check_update_manual)
        m.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))

    # ═══════════════════════════════════════════════════════
    #  FILE OPERATIONS
    # ═══════════════════════════════════════════════════════

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Macro", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "w") as f:
                    json.dump([a.to_dict() for a in self.engine.actions], f, indent=2)
                self.status(f"Exported {len(self.engine.actions)} actions")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Macro", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                self.history.push(self.engine.actions)
                self.engine.actions = [Action.from_dict(x) for x in data]
                self.active_index = -1
                self.timeline.set_actions(self.engine.actions)
                self.timeline.refresh()
                self.refresh()
                self.update_statistics()
                self.save_session()
                self.status(f"Imported {len(self.engine.actions)} actions")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))

    def export_csv(self):
        if not self.engine.actions:
            QMessageBox.warning(self, "No Actions", "Nothing to export")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV (*.csv)")
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["index", "key", "duration", "hold", "lane", "rand_delay", "rand_key", "type", "label"])
                    for i, a in enumerate(self.engine.actions):
                        writer.writerow([i+1, a.key, a.duration, a.hold_mode, a.lane, a.random_delay, a.random_key, a.action_type, a.label])
                self.status(f"Exported {len(self.engine.actions)} actions to CSV")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV (*.csv)")
        if path:
            try:
                self.history.push(self.engine.actions)
                new_actions = []
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        a = Action(
                            key=row["key"],
                            duration=float(row["duration"]),
                            hold_mode=row.get("hold", "False") == "True",
                            lane=int(row.get("lane", 0)),
                            random_delay=float(row.get("rand_delay", 0)),
                            random_key=row.get("rand_key", "False") == "True",
                            action_type=row.get("type", "key"),
                            label=row.get("label", "")
                        )
                        new_actions.append(a)
                self.engine.actions = new_actions
                self.active_index = -1
                self.timeline.set_actions(self.engine.actions)
                self.timeline.refresh()
                self.refresh()
                self.update_statistics()
                self.save_session()
                self.status(f"Imported {len(new_actions)} actions from CSV")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))

    def clear_all(self):
        if QMessageBox.question(self, "Clear All",
            "Remove all actions?") == QMessageBox.StandardButton.Yes:
            self.history.push(self.engine.actions)
            self.engine.actions.clear()
            self.active_index = -1
            self.timeline.selected_indices.clear()
            self.refresh()
            self.update_statistics()
            self.save_session()
            self.status("All actions cleared")

    def reset_stats(self):
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = None
        self.update_statistics(immediate=True)
        self.status("Statistics reset")

    # ═══════════════════════════════════════════════════════
    #  UPDATE CHECKING
    # ═══════════════════════════════════════════════════════

    def _check_update_silent(self):
        self._update_prompt_shown = False  # fresh startup = allow prompt
        def _bg():
            try:
                manifest = check_update(silent=True)
                if manifest:
                    self._update_found.emit(manifest)
            except Exception as e:
                logger.error(f"Silent update check failed: {e}")
        threading.Thread(target=_bg, daemon=True).start()

    def _on_update_found(self, manifest):
        """Slot for _update_found signal — always runs on main thread."""
        self._set_update_done()
        self._prompt_update(manifest)

    def _on_update_not_found(self):
        self._set_update_done()
        self.status("No updates found")

    def _on_update_error(self, error_msg):
        self._set_update_done()
        self._on_close_update_dlg()
        QMessageBox.warning(self, "Update Check Failed", f"Could not check for updates:\n\n{error_msg}")

    def _on_close_update_dlg(self):
        if hasattr(self, '_update_dlg') and self._update_dlg:
            self._update_dlg.close()
            self._update_dlg = None
        if hasattr(self, '_update_bar'):
            self._update_bar = None
        if hasattr(self, '_update_info'):
            self._update_info = None
        try:
            self._download_progress.disconnect(self._on_download_progress)
        except Exception:
            pass

    def _on_download_progress(self, pct, txt):
        """Slot for _download_progress signal — always runs on main thread."""
        if hasattr(self, '_update_bar') and self._update_bar:
            self._update_bar.setValue(pct)
        if hasattr(self, '_update_info') and self._update_info:
            self._update_info.setText(txt)

    def _set_update_done(self):
        self._update_checking = False

    def _check_update_manual(self):
        if getattr(self, "_update_checking", False):
            self.status("Already checking for updates")
            return
        self._update_checking = True
        self._update_prompt_shown = False  # allow re-prompt on fresh check
        self.status("Checking for updates…")

        def _bg():
            try:
                manifest = check_update(silent=False)
            except Exception as e:
                self._update_error.emit(str(e))
                return
            if manifest:
                self._update_found.emit(manifest)
            else:
                error = get_last_update_error()
                if error:
                    self._update_error.emit(error)
                else:
                    self._update_not_found.emit()

        threading.Thread(target=_bg, daemon=True).start()
        # Safety net: reset flag after 30s so UI isn't stuck
        QTimer.singleShot(30000, lambda: self._set_update_done() if getattr(self, "_update_checking", False) else None)

    def _prompt_update(self, manifest):
        try:
            # Allow re-prompting on a fresh check (flag is reset when check starts)
            if getattr(self, "_update_prompt_shown", False):
                logger.info("Update prompt already shown, skipping duplicate")
                return
            self._update_prompt_shown = True
            logger.info("Showing update prompt")

            remote_ver = manifest.get("version", "unknown")
            notes = manifest.get("notes", "")
            msg = f"A new version of MacroForge is available.\n\nCurrent: {VERSION}\nLatest: {remote_ver}"
            if notes:
                msg += f"\n\nRelease notes:\n{notes}"
            msg += "\n\nDownload and install now?"

            box = QMessageBox(self)
            box.setWindowTitle("Update Available")
            box.setText(msg)
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.Yes)
            box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            reply = box.exec()
            logger.info(f"Update prompt result: {reply}")

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Progress dialog
            self._update_dlg = QDialog(self)
            self._update_dlg.setWindowTitle("Updating MacroForge")
            self._update_dlg.setFixedSize(380, 140)
            self._update_dlg.setStyleSheet(f"QDialog {{ background-color: {COLORS['bg_secondary']}; }}")
            self._update_dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            lo = QVBoxLayout(self._update_dlg)
            lo.setContentsMargins(16, 16, 16, 16)
            lo.addWidget(QLabel(f"Downloading MacroForge {remote_ver}…"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(8)
            lo.addWidget(bar)
            info = QLabel("Starting…")
            info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
            lo.addWidget(info)
            self._update_dlg.show()
            self._update_dlg.raise_()
            self._update_dlg.activateWindow()
            self._update_dlg.update()
            QApplication.processEvents()

            # Store refs for signal-based updates (thread-safe)
            self._update_bar = bar
            self._update_info = info
            try:
                self._download_progress.disconnect(self._on_download_progress)
            except Exception:
                pass
            self._download_progress.connect(self._on_download_progress)

            def _on_progress(downloaded, total):
                pct = downloaded / total * 100 if total else 0
                mb_down = downloaded / (1024 * 1024)
                if total:
                    mb_total = total / (1024 * 1024)
                    txt = f"{mb_down:.1f} MB / {mb_total:.1f} MB  ({pct:.0f}%)"
                else:
                    txt = f"{mb_down:.1f} MB downloaded"
                self._download_progress.emit(int(pct), txt)

            def _download():
                try:
                    if perform_update(manifest, progress_cb=_on_progress):
                        self._close_update_dlg.emit()
                        self._do_exit.emit()
                    else:
                        self._close_update_dlg.emit()
                        self._update_error.emit("Download or installation failed. See debug log for details.")
                except Exception as e:
                    logger.error(f"perform_update failed: {e}")
                    self._close_update_dlg.emit()
                    self._update_error.emit(f"Update failed: {e}")
            threading.Thread(target=_download, daemon=True).start()
        except Exception as e:
            logger.error(f"_prompt_update crashed: {e}")
            self._update_prompt_shown = False

    # ═══════════════════════════════════════════════════════
    #  STATISTICS & STATUS
    # ═══════════════════════════════════════════════════════

    def status(self, msg):
        # Thread-safe: always marshal Qt widget access to main thread
        QTimer.singleShot(0, lambda: self.status_text.setText(msg))
        logger.info(msg)

    def _invalidate_seq_dur(self):
        self._seq_dur_cache = sum(a.duration for a in self.engine.actions)

    @staticmethod
    def _format_hms(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h}:{m:02d}:{s:02d}"

    def update_statistics(self, immediate=False):
        seq_dur = getattr(self, '_seq_dur_cache', 0.0)
        loops_done = getattr(self.engine, 'loops_completed_count', 0)
        session_time = seq_dur * loops_done

        self._stat_actions.setText(str(self.actions_played))
        self._stat_loops.setText(str(loops_done))
        self._stat_seq.setText(f"{seq_dur:.1f}s")
        self._stat_time.setText(self._format_hms(session_time))

    # ═══════════════════════════════════════════════════════
    #  HOTKEYS & SYSTRAY
    # ═══════════════════════════════════════════════════════

    def _setup_hotkeys(self):
        try:
            start_hotkeys({
                "f9": self._hotkey_toggle_play,
                "f7": self._hotkey_record,
            })
        except Exception as e:
            logger.warning(f"Hotkeys not available: {e}")

    def _hotkey_toggle_play(self):
        if self.engine.running:
            self.stop()
        else:
            self.start()

    def _hotkey_record(self):
        self._toggle_record()

    def _setup_tray(self):
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
            from PyQt6.QtGui import QIcon
            self._tray_menu = QMenu()
            self._tray_menu.addAction("Show", self.showNormal)
            self._tray_menu.addAction("Quit", self._real_exit)
            self._tray_icon = QSystemTrayIcon(self)
            self._tray_icon.setContextMenu(self._tray_menu)
            self._tray_icon.setIcon(self.windowIcon())
            self._tray_icon.activated.connect(self._tray_activated)
            self._tray_icon.show()
        except Exception as e:
            logger.debug(f"Tray not available: {e}")

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()

    # ═══════════════════════════════════════════════════════
    #  UTILITIES
    # ═══════════════════════════════════════════════════════

    def refresh(self):
        self._invalidate_seq_dur()
        self.timeline.set_actions(self.engine.actions)
        self.update_statistics()

    def open_debug_viewer(self):
        try:
            from debugger import DebugViewer
            dv = DebugViewer(self)
            dv.show()
        except Exception as e:
            logger.error(f"Debug viewer: {e}")

    def open_settings_dialog(self):
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, self.settings_manager)
        dlg.exec()

    # ═══════════════════════════════════════════════════════
    #  DIALOGS
    # ═══════════════════════════════════════════════════════

    def _open_key_dialog(self):
        try:
            from ui.dialogs.key_dialog import KeyDialog
            dlg = KeyDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.engine.actions)
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.refresh()
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status(f"Added key: {act.key}")
        except Exception as e:
            logger.error(f"_open_key_dialog: {e}")
            raise

    def _open_click_dialog(self):
        try:
            from ui.dialogs.click_dialog import ClickDialog
            dlg = ClickDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.engine.actions)
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.refresh()
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status("Added click")
        except Exception as e:
            logger.error(f"_open_click_dialog: {e}")
            raise

    def _open_pause_dialog(self):
        try:
            from ui.dialogs.pause_dialog import PauseDialog
            dlg = PauseDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.engine.actions)
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.refresh()
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status("Added delay")
        except Exception as e:
            logger.error(f"_open_pause_dialog: {e}")
            raise

    def _open_image_dialog(self):
        try:
            from ui.dialogs.image_dialog import ImageDialog
            dlg = ImageDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.engine.actions)
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.refresh()
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status("Added image search")
        except Exception as e:
            logger.error(f"_open_image_dialog: {e}")
            raise

    def _open_capture_dialog(self):
        try:
            from ui.dialogs.image_dialog import ImageDialog
            dlg = ImageDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                act = dlg.get_action()
                if act:
                    self.history.push(self.engine.actions)
                    self.engine.actions.append(act)
                    self.active_index = len(self.engine.actions) - 1
                    self.refresh()
                    self.timeline.ensure_visible(self.active_index)
                    self.save_session()
                    self.status("Added captured image search")
        except Exception as e:
            logger.error(f"_open_capture_dialog: {e}")
            raise

    def _open_key_editor(self, index):
        from ui.dialogs.key_dialog import KeyDialog
        dlg = KeyDialog(self, existing=self.engine.actions[index])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self.history.push(self.engine.actions)
                self.engine.actions[index] = act
                self.refresh()
                self.save_session()
                self.status("Key action updated")

    def _open_click_editor(self, index):
        from ui.dialogs.click_dialog import ClickDialog
        dlg = ClickDialog(self, existing=self.engine.actions[index])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self.history.push(self.engine.actions)
                self.engine.actions[index] = act
                self.refresh()
                self.save_session()
                self.status("Click action updated")

    def _open_pause_editor(self, index):
        from ui.dialogs.pause_dialog import PauseDialog
        dlg = PauseDialog(self, existing=self.engine.actions[index])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self.history.push(self.engine.actions)
                self.engine.actions[index] = act
                self.refresh()
                self.save_session()
                self.status("Delay action updated")

    def _open_image_editor(self, index):
        from ui.dialogs.image_dialog import ImageDialog
        dlg = ImageDialog(self, existing=self.engine.actions[index])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.get_action()
            if act:
                self.history.push(self.engine.actions)
                self.engine.actions[index] = act
                self.refresh()
                self.save_session()
                self.status("Image action updated")

    def _real_exit(self):
        try:
            self._do_save_session()
        except Exception:
            pass
        try:
            stop_hotkeys()
        except Exception:
            pass
        try:
            if self._tray_icon:
                self._tray_icon.hide()
                self._tray_icon = None
        except Exception:
            pass
        try:
            for w in QApplication.topLevelWidgets():
                w.close()
        except Exception:
            pass
        try:
            QApplication.quit()
        except Exception:
            pass
        os._exit(0)

    def closeEvent(self, event):
        self._do_save_session()
        try:
            stop_hotkeys()
        except Exception:
            pass
        event.accept()

    def undo(self):
        if not self.history.can_undo():
            self.status("Nothing to undo")
            return
        result = self.history.undo(self.engine.actions)
        if result is None:
            return
        self.engine.actions = result
        self.active_index = -1
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Undone")

    def redo(self):
        if not self.history.can_redo():
            self.status("Nothing to redo")
            return
        result = self.history.redo(self.engine.actions)
        if result is None:
            return
        self.engine.actions = result
        self.active_index = -1
        self.refresh()
        self.update_statistics()
        self.save_session()
        self.status("Redone")


class HistoryManager:
    """Simple undo/redo stack."""
    def __init__(self, max_size=50):
        self._undo = []
        self._redo = []
        self._max = max_size

    def push(self, actions):
        import copy
        self._undo.append([a.to_dict() for a in actions])
        if len(self._undo) > self._max:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self, current_actions):
        if not self._undo:
            return None
        self._redo.append([a.to_dict() for a in current_actions])
        data = self._undo.pop()
        return [Action.from_dict(d) for d in data]

    def redo(self, current_actions):
        if not self._redo:
            return None
        self._undo.append([a.to_dict() for a in current_actions])
        data = self._redo.pop()
        return [Action.from_dict(d) for d in data]

