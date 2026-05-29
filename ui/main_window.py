"""Main window for MacroForge PyQt6 UI.

Rebuilt from v1.1.0 tkinter version with all features preserved
and new PyQt6 animations, modern styling, and UX improvements.
"""
import time
import threading
import queue
from copy import deepcopy

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSplitter, QSystemTrayIcon, QMenu, QMessageBox,
    QFileDialog, QSlider, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QIcon, QShortcut

from ui.theme import COLORS, build_stylesheet, TYPE_COLORS
from ui.animations import Animator
from version import VERSION
from debugger import logger

# Dialog imports (created later)
from ui.dialogs.key_editor import KeyEditorDialog
from ui.dialogs.click_editor import ClickEditorDialog
from ui.dialogs.pause_editor import PauseEditorDialog
from ui.dialogs.image_editor import ImageEditorDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.log_viewer import LogViewerDialog

# Backend
from models import Config, Action, HistoryManager, ProfileManager, SettingsManager
from engine import ExecutionEngine


class MainWindow(QMainWindow):
    """Modern PyQt6 main window for MacroForge."""

    def __init__(self):
        super().__init__()

        # DPI awareness
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        # Backend init
        self.config = Config()
        self.session_manager = ProfileManager()
        self.settings_manager = SettingsManager(self.session_manager.base_dir)

        _s = self.settings_manager.all()
        self.auto_save_enabled = _s.get("auto_save", True)
        self._default_loops = _s.get("default_loops", 1)
        self._default_speed = _s.get("default_speed", 1.0)

        self.engine = ExecutionEngine(
            self._on_status,
            self._on_play,
            self._on_complete,
            self._on_progress,
        )
        self.history = HistoryManager()
        self.clipboard_action = None

        self._active_index = -1
        self._countdown_active = False
        self._save_timer = None
        self._ui_timer = None
        self._pending_status = None
        self._engine_thread = None
        self._pending_update = None
        self._rec_anim = None

        # Recorder state
        self._recorder = {
            "running": False, "paused": False, "queue": None,
            "presses": {}, "modifiers": set(), "last_time": 0.0,
            "thread": None,
        }

        self.setWindowTitle(f"MacroForge v{VERSION}")
        self.setMinimumSize(900, 700)
        self.resize(1100, 800)
        self.setStyleSheet(build_stylesheet())

        self._setup_central_widget()
        self._setup_sidebar()
        self._setup_toolbar()
        self._setup_action_bar()
        self._setup_content_area()
        self._setup_tray()
        self._setup_hotkeys()

        self.engine.before_action_hook = self._before_action
        self.engine.pause_cb = self._on_pause_changed
        self.engine._flash_cb = self._flash_match

        # Load session
        self._load_last_session()
        self._update_window_title()

        # Background update check
        QTimer.singleShot(3000, self._check_update_silent)

    # ═══════════════════════════════════════════════════════
    #  UI SETUP
    # ═══════════════════════════════════════════════════════

    def _setup_central_widget(self):
        central = QWidget()
        self.setCentralWidget(central)
        self._main_layout = QHBoxLayout(central)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Toast overlay (child of central, positioned manually)
        self._toast = QLabel(central)
        self._toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast.setStyleSheet(f"""
            background-color: {COLORS['bg_tertiary']};
            color: {COLORS['text']};
            border: 1px solid {COLORS['border_light']};
            border-radius: 10px;
            padding: 10px 20px;
            font-size: 13px;
        """)
        self._toast.hide()
        self._toast_timer = None

    def _setup_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(f"""
            QFrame#sidebar {{
                background-color: {COLORS['bg_secondary']};
                border-right: 1px solid {COLORS['border']};
                min-width: 200px;
                max-width: 200px;
            }}
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Brand
        brand = QLabel("MACROFORGE")
        brand.setStyleSheet(f"color: {COLORS['accent']}; font-size: 16px; font-weight: bold; letter-spacing: 2px;")
        layout.addWidget(brand)

        # Subtitle
        sub = QLabel("Macro Automation")
        sub.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 10px; margin-bottom: 8px;")
        layout.addWidget(sub)

        layout.addSpacing(12)

        # Nav buttons
        self._nav_buttons = {}
        for name, label, tip in [
            ("macro", "🎬  Macro", "Macro editor"),
            ("settings", "⚙  Settings", "Open settings"),
            ("logs", "📝  Logs", "View debug logs"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(name == "macro")
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    padding: 10px 14px;
                    border-radius: 8px;
                    background: transparent;
                    border: none;
                    color: {COLORS['text_dim']};
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['bg_hover']};
                    color: {COLORS['text']};
                }}
                QPushButton:checked {{
                    background-color: {COLORS['accent_glow']};
                    color: {COLORS['accent']};
                    font-weight: 600;
                }}
            """)
            btn.clicked.connect(lambda checked, n=name: self._switch_page(n))
            layout.addWidget(btn)
            self._nav_buttons[name] = btn

        layout.addStretch(1)

        # Version
        ver = QLabel(f"v{VERSION}")
        ver.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 10px;")
        layout.addWidget(ver)

        self._main_layout.addWidget(sidebar)

    def _setup_toolbar(self):
        toolbar = QFrame()
        toolbar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Profile selector
        layout.addWidget(QLabel("Profile:"))
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(140)
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)
        layout.addWidget(self._profile_combo)

        self._btn_rename = QPushButton("✏️")
        self._btn_rename.setObjectName("tool")
        self._btn_rename.setToolTip("Rename profile")
        self._btn_rename.clicked.connect(self._rename_profile)
        layout.addWidget(self._btn_rename)

        self._btn_new = QPushButton("➕")
        self._btn_new.setObjectName("tool")
        self._btn_new.setToolTip("New profile")
        self._btn_new.clicked.connect(self._new_profile)
        layout.addWidget(self._btn_new)

        self._btn_del_prof = QPushButton("🗑️")
        self._btn_del_prof.setObjectName("tool")
        self._btn_del_prof.setToolTip("Delete profile")
        self._btn_del_prof.clicked.connect(self._delete_profile)
        layout.addWidget(self._btn_del_prof)

        layout.addSpacing(16)
        layout.addWidget(self._vline())
        layout.addSpacing(16)

        # Transport buttons
        self._btn_play = QPushButton("▶  Play")
        self._btn_play.setObjectName("accent")
        self._btn_play.setToolTip("F5 — Start playback")
        self._btn_play.clicked.connect(self._on_play_clicked)
        layout.addWidget(self._btn_play)

        self._btn_stop = QPushButton("⏹  Stop")
        self._btn_stop.setObjectName("tool")
        self._btn_stop.setToolTip("F6 — Stop playback")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self._btn_stop)

        self._btn_record = QPushButton("●  Record")
        self._btn_record.setObjectName("danger")
        self._btn_record.setCheckable(True)
        self._btn_record.setToolTip("F7 — Start recording, F9 — Stop")
        self._btn_record.clicked.connect(self._on_record_clicked)
        layout.addWidget(self._btn_record)

        layout.addSpacing(16)
        layout.addWidget(self._vline())
        layout.addSpacing(16)

        # Loop & speed
        layout.addWidget(QLabel("Loops:"))
        self._spin_loop = QSpinBox()
        self._spin_loop.setRange(1, 9999)
        self._spin_loop.setValue(self._default_loops)
        self._spin_loop.setMinimumWidth(60)
        layout.addWidget(self._spin_loop)

        self._chk_infinite = QCheckBox("∞")
        self._chk_infinite.setToolTip("Infinite loop")
        self._chk_infinite.stateChanged.connect(self._on_infinite_changed)
        layout.addWidget(self._chk_infinite)

        layout.addWidget(QLabel("Speed:"))
        self._spin_speed = QDoubleSpinBox()
        self._spin_speed.setRange(0.1, 10.0)
        self._spin_speed.setValue(self._default_speed)
        self._spin_speed.setSingleStep(0.1)
        self._spin_speed.setDecimals(2)
        self._spin_speed.setMinimumWidth(70)
        self._spin_speed.valueChanged.connect(self._on_speed_changed)
        layout.addWidget(self._spin_speed)

        layout.addSpacing(16)
        layout.addWidget(self._vline())
        layout.addSpacing(16)

        # Toggles
        self._chk_sim = QCheckBox("Sim")
        self._chk_sim.setToolTip("Simulation mode")
        layout.addWidget(self._chk_sim)

        self._chk_focus = QCheckBox("Focus")
        self._chk_focus.setToolTip("Focus lock")
        layout.addWidget(self._chk_focus)

        self._chk_human = QCheckBox("Human")
        self._chk_human.setToolTip("Human-like curves")
        self._chk_human.setChecked(True)
        self._chk_human.stateChanged.connect(self._on_human_changed)
        layout.addWidget(self._chk_human)

        layout.addStretch(1)

        # Right-side buttons
        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setObjectName("tool")
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(self._btn_settings)

        self._btn_logs = QPushButton("📝")
        self._btn_logs.setObjectName("tool")
        self._btn_logs.setToolTip("Debug Logs")
        self._btn_logs.clicked.connect(self._open_logs)
        layout.addWidget(self._btn_logs)

        self._btn_update = QPushButton("🔄")
        self._btn_update.setObjectName("tool")
        self._btn_update.setToolTip("Check for updates")
        self._btn_update.clicked.connect(self._check_update_manual)
        layout.addWidget(self._btn_update)

        self._toolbar = toolbar

    def _setup_action_bar(self):
        bar = QFrame()
        bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Add:"))
        for label, method in [
            ("⌨️ Key", self.add_key_action),
            ("🖱️ Click", self.add_click_action),
            ("⏱️ Delay", self.add_pause_action),
            ("🖼️ Image", self.add_image_action),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("tool")
            btn.clicked.connect(method)
            layout.addWidget(btn)

        layout.addSpacing(12)
        layout.addWidget(self._vline())
        layout.addSpacing(12)

        for label, method in [
            ("📋 Duplicate", self._duplicate_selected),
            ("🗑️ Delete", self._delete_selected),
            ("⬆️ Up", self._move_up_selected),
            ("⬇️ Down", self._move_down_selected),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("tool")
            btn.clicked.connect(method)
            layout.addWidget(btn)

        layout.addStretch(1)

        layout.addWidget(self._vline())
        layout.addSpacing(12)

        for label, method in [
            ("📤 CSV", self.export_csv),
            ("📥 CSV", self.import_csv),
            ("💾 JSON", self.save_json),
            ("📂 JSON", self.load_json),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("tool")
            btn.clicked.connect(method)
            layout.addWidget(btn)

        self._action_bar = bar

    def _setup_content_area(self):
        from ui.action_table import ActionTable
        from ui.timeline_widget import TimelineWidget
        from ui.properties_panel import PropertiesPanel

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Toolbar + action bar
        content_layout.addWidget(self._toolbar)
        content_layout.addWidget(self._action_bar)

        # Horizontal splitter: left (table+timeline) | right (properties)
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: vertical splitter (table top, timeline bottom)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._action_table = ActionTable()
        self._action_table.action_selected.connect(self._on_table_select)
        self._action_table.action_double_clicked.connect(self._on_table_double_click)
        self._action_table.action_context_menu.connect(self._on_table_context)
        left_layout.addWidget(self._action_table, 3)

        self._timeline = TimelineWidget()
        self._timeline.action_clicked.connect(self._on_timeline_click)
        left_layout.addWidget(self._timeline, 1)

        h_splitter.addWidget(left)

        # Right: properties panel
        self._properties = PropertiesPanel()
        self._properties.action_changed.connect(self._on_properties_changed)
        h_splitter.addWidget(self._properties)
        h_splitter.setSizes([700, 300])

        content_layout.addWidget(h_splitter, 1)

        # Status bar
        content_layout.addWidget(self._build_status_strip())

        self._main_layout.addWidget(content, 1)

    def _build_status_strip(self):
        status = QFrame()
        status.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(12, 6, 12, 6)
        status_layout.setSpacing(16)

        self._lbl_status = QLabel("Ready")
        self._lbl_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        status_layout.addWidget(self._lbl_status)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setMaximumWidth(180)
        self._progress.setMinimumHeight(4)
        self._progress.setEnabled(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['border']};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent']};
                border-radius: 2px;
            }}
        """)
        status_layout.addWidget(self._progress)

        self._lbl_stats = QLabel("0 actions | 0:00 | 0 loops")
        self._lbl_stats.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        status_layout.addWidget(self._lbl_stats)

        status_layout.addStretch(1)

        self._lbl_version = QLabel(f"v{VERSION}")
        self._lbl_version.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 11px;")
        status_layout.addWidget(self._lbl_version)

        return status

    def _vline(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet(f"color: {COLORS['border']};")
        line.setMaximumWidth(1)
        return line

    # ═══════════════════════════════════════════════════════
    #  HOTKEYS & SHORTCUTS
    # ═══════════════════════════════════════════════════════

    def _setup_hotkeys(self):
        shortcuts = [
            (QKeySequence("Ctrl+Z"), self._undo),
            (QKeySequence("Ctrl+Y"), self._redo),
            (QKeySequence("Ctrl+C"), self._copy_selected),
            (QKeySequence("Ctrl+V"), self._paste_selected),
            (QKeySequence("Ctrl+D"), self._duplicate_selected),
            (QKeySequence("Ctrl+S"), self._quick_save),
            (QKeySequence("Delete"), self._delete_selected),
            (QKeySequence("Ctrl+F"), self._focus_table),
            (QKeySequence("Esc"), self._on_escape),
        ]
        for seq, slot in shortcuts:
            sc = QShortcut(seq, self)
            sc.activated.connect(slot)

        # Global hotkeys via pynput
        try:
            from pynput import keyboard
            self._hotkey_listener = keyboard.GlobalHotKeys({
                "<f5>": lambda: self._on_play_clicked(),
                "<f6>": lambda: self._on_stop_clicked(),
                "<f7>": lambda: self._on_record_clicked() if not self._recorder["running"] else None,
                "<f9>": lambda: self._on_record_clicked() if self._recorder["running"] else None,
            })
            self._hotkey_listener.start()
        except Exception as e:
            logger.error(f"Hotkey init failed: {e}")

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("MacroForge")
        if QIcon("MacroForge.ico"):
            self._tray.setIcon(QIcon("MacroForge.ico"))
        tray_menu = QMenu(self)
        tray_menu.addAction("Show", self.showNormal)
        tray_menu.addAction("Play", self._on_play_clicked)
        tray_menu.addAction("Stop", self._on_stop_clicked)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", self.close)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    # ═══════════════════════════════════════════════════════
    #  PAGE SWITCHING
    # ═══════════════════════════════════════════════════════

    def _switch_page(self, page: str):
        for p, btn in self._nav_buttons.items():
            btn.setChecked(p == page)
        if page == "settings":
            self._open_settings()
        elif page == "logs":
            self._open_logs()
        self._nav_buttons["macro"].setChecked(True)

    # ═══════════════════════════════════════════════════════
    #  EVENT HANDLERS
    # ═══════════════════════════════════════════════════════

    def _on_profile_changed(self, name: str):
        if not name or name == self.session_manager.active:
            return
        self._switch_profile(name)

    def _on_play_clicked(self):
        if self.engine.running:
            if self.engine.paused:
                self.engine.toggle_pause()
                self._btn_play.setEnabled(False)
                self._btn_stop.setEnabled(True)
                self._on_status("Resumed")
            return
        if not self.engine.actions:
            QMessageBox.warning(self, "No Actions", "Add some actions first.")
            return
        self._countdown_active = True
        self._btn_play.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._run_countdown(3)

    def _run_countdown(self, n: int):
        if not self._countdown_active:
            self._btn_play.setEnabled(True)
            return
        if n > 0:
            self._on_status(f"Starting in {n}...  (Esc to cancel)")
            QTimer.singleShot(1000, lambda: self._run_countdown(n - 1))
        else:
            self._countdown_active = False
            self._start_playback()

    def _start_playback(self):
        loops = 999999 if self._chk_infinite.isChecked() else self._spin_loop.value()
        self.engine.speed_multiplier = self._spin_speed.value()
        self.engine.infinite_loop = self._chk_infinite.isChecked()
        self.engine.simulation_mode = self._chk_sim.isChecked()
        self.engine.focus_lock = self._chk_focus.isChecked()
        self.engine.human_curve = self._chk_human.isChecked()
        if self.engine.focus_lock:
            self.engine.capture_focus_window()
        self._btn_play.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_record.setEnabled(False)
        self._progress.setValue(0)
        self._progress.setEnabled(True)
        self._engine_thread = threading.Thread(target=self.engine.run, args=(loops,), daemon=True)
        self._engine_thread.start()

    def _on_stop_clicked(self):
        self.engine.running = False
        self.engine.paused = False
        self._btn_play.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_record.setEnabled(True)
        self._timeline.clear_playing()
        self._action_table.set_playing_index(-1)
        self._progress.setValue(0)
        self._progress.setEnabled(False)
        self._on_status("Stopped")

    def _on_record_clicked(self):
        if self._btn_record.isChecked() and not self._recorder["running"]:
            self._start_recording()
        elif not self._btn_record.isChecked() and self._recorder["running"]:
            self._stop_recording()

    def _on_infinite_changed(self, state):
        self._spin_loop.setEnabled(state == Qt.CheckState.Unchecked.value)

    def _on_speed_changed(self, val):
        self.engine.speed_multiplier = val

    def _on_human_changed(self, state):
        self.engine.human_curve = (state == Qt.CheckState.Checked.value)

    def _on_status(self, msg: str):
        self._pending_status = msg
        if self._ui_timer is None:
            self._ui_timer = QTimer.singleShot(50, self._flush_status)
        self._show_toast(msg)

    def _flush_status(self):
        if self._pending_status:
            self._lbl_status.setText(self._pending_status)
            self._pending_status = None
        self._ui_timer = None

    def _show_toast(self, msg: str, duration: int = 2000):
        self._toast.setText(msg)
        self._toast.adjustSize()
        parent = self._toast.parent()
        if parent:
            x = (parent.width() - self._toast.width()) // 2
            y = parent.height() - self._toast.height() - 50
            self._toast.move(x, y)
        self._toast.show()
        Animator.fade_in(self._toast, 200)
        if self._toast_timer:
            self._toast_timer.stop()
        self._toast_timer = QTimer()
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._hide_toast)
        self._toast_timer.start(duration)

    def _hide_toast(self):
        Animator.fade_out(self._toast, 200, lambda: self._toast.hide())

    def _on_play(self, index: int):
        if 0 <= index < len(self.engine.actions):
            action = self.engine.actions[index]
            dur = getattr(action, "duration", 0.0)
            self._timeline.set_playing(index, dur)
            self._action_table.set_playing_index(index)
            pct = int((index + 1) / max(1, len(self.engine.actions)) * 100)
            self._progress.setValue(pct)

    def _on_complete(self):
        self._btn_play.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_record.setEnabled(True)
        self._timeline.clear_playing()
        self._action_table.set_playing_index(-1)
        self._progress.setValue(100)
        self._progress.setEnabled(False)
        self._update_statistics()
        self._on_status("Playback complete")

    def _on_progress(self, pct: float):
        self._progress.setValue(int(pct))

    def _on_pause_changed(self, paused: bool):
        self._on_status("Paused" if paused else "Resumed")

    def _before_action(self, action: Action):
        pass

    def _flash_match(self, loc):
        pass  # Could flash region on screen

    # ═══════════════════════════════════════════════════════
    #  TABLE / TIMELINE SELECTION
    # ═══════════════════════════════════════════════════════

    def _on_timeline_click(self, index: int):
        self._select_action(index)

    def _on_table_select(self, index: int):
        self._select_action(index)

    def _on_table_double_click(self, index: int):
        self._edit_action(index)

    def _on_table_context(self, index: int, pos):
        menu = QMenu(self)
        menu.addAction("Edit", lambda: self._edit_action(index))
        menu.addAction("Duplicate", lambda: self._duplicate_action(index))
        menu.addAction("Copy", lambda: self._copy_action(index))
        menu.addAction("Paste After", lambda: self._paste_action(index))
        menu.addSeparator()
        menu.addAction("Move Up", lambda: self._move_action(index, index - 1))
        menu.addAction("Move Down", lambda: self._move_action(index, index + 1))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self._delete_action(index))
        if pos:
            menu.exec(pos)
        else:
            menu.exec(self.cursor().pos())

    def _on_properties_changed(self):
        self._action_table.set_actions(self.engine.actions)
        self._timeline.set_actions(self.engine.actions)
        self._update_statistics()
        self._save_session()

    # ═══════════════════════════════════════════════════════
    #  ACTION CRUD
    # ═══════════════════════════════════════════════════════

    def _select_action(self, index: int):
        self._active_index = index
        self._action_table.set_active_index(index)
        self._timeline.set_active_index(index)
        if 0 <= index < len(self.engine.actions):
            self._properties.set_action(self.engine.actions[index])
        else:
            self._properties.set_action(None)

    def _edit_action(self, index: int):
        if not (0 <= index < len(self.engine.actions)):
            return
        action = self.engine.actions[index]
        t = getattr(action, "action_type", "key")
        dlg = None
        if t == "key":
            dlg = KeyEditorDialog(self, action)
        elif t == "click":
            dlg = ClickEditorDialog(self, action)
        elif t == "pause":
            dlg = PauseEditorDialog(self, action)
        elif t == "image":
            dlg = ImageEditorDialog(self, action)
        if dlg and dlg.exec():
            self._action_table.set_actions(self.engine.actions)
            self._timeline.set_actions(self.engine.actions)
            self._update_statistics()
            self._save_session()

    def _duplicate_action(self, index: int):
        if not (0 <= index < len(self.engine.actions)):
            return
        self.history.push(self.engine.actions)
        new_action = deepcopy(self.engine.actions[index])
        self.engine.actions.insert(index + 1, new_action)
        self._refresh_all()
        self._select_action(index + 1)
        self._save_session()

    def _copy_action(self, index: int):
        if not (0 <= index < len(self.engine.actions)):
            return
        self.clipboard_action = deepcopy(self.engine.actions[index])
        self._on_status("Copied action")

    def _paste_action(self, index: int):
        if self.clipboard_action is None:
            self._on_status("Clipboard empty")
            return
        self.history.push(self.engine.actions)
        new_action = deepcopy(self.clipboard_action)
        insert_at = index + 1 if 0 <= index < len(self.engine.actions) else len(self.engine.actions)
        self.engine.actions.insert(insert_at, new_action)
        self._refresh_all()
        self._select_action(insert_at)
        self._save_session()

    def _move_action(self, index: int, target: int):
        if not (0 <= index < len(self.engine.actions)):
            return
        if not (0 <= target < len(self.engine.actions)):
            return
        self.history.push(self.engine.actions)
        action = self.engine.actions.pop(index)
        self.engine.actions.insert(target, action)
        self._refresh_all()
        self._select_action(target)
        self._save_session()

    def _delete_action(self, index: int):
        if not (0 <= index < len(self.engine.actions)):
            return
        self.history.push(self.engine.actions)
        del self.engine.actions[index]
        self._refresh_all()
        self._select_action(min(index, len(self.engine.actions) - 1))
        self._save_session()

    # ═══════════════════════════════════════════════════════
    #  KEYBOARD SHORTCUT HELPERS
    # ═══════════════════════════════════════════════════════

    def _undo(self):
        if not self.history.can_undo():
            self._on_status("Nothing to undo")
            return
        result = self.history.undo(self.engine.actions)
        if result is not None:
            self.engine.actions = result
            self._refresh_all()
            self._select_action(-1)
            self._save_session()
            self._on_status("Undone")

    def _redo(self):
        if not self.history.can_redo():
            self._on_status("Nothing to redo")
            return
        result = self.history.redo(self.engine.actions)
        if result is not None:
            self.engine.actions = result
            self._refresh_all()
            self._select_action(-1)
            self._save_session()
            self._on_status("Redone")

    def _copy_selected(self):
        idx = getattr(self, '_active_index', -1)
        if idx >= 0:
            self._copy_action(idx)

    def _paste_selected(self):
        idx = getattr(self, '_active_index', -1)
        self._paste_action(idx)

    def _duplicate_selected(self):
        idx = getattr(self, '_active_index', -1)
        if idx >= 0:
            self._duplicate_action(idx)

    def _delete_selected(self):
        idx = getattr(self, '_active_index', -1)
        if idx >= 0:
            self._delete_action(idx)

    def _move_up_selected(self):
        idx = getattr(self, '_active_index', -1)
        if idx > 0:
            self._move_action(idx, idx - 1)

    def _move_down_selected(self):
        idx = getattr(self, '_active_index', -1)
        if 0 <= idx < len(self.engine.actions) - 1:
            self._move_action(idx, idx + 1)

    def _quick_save(self):
        self._do_save()
        self._on_status("Session saved")

    def _focus_table(self):
        self._action_table.setFocus()
        self._on_status("Table focused")

    def _on_escape(self):
        if self._countdown_active:
            self._countdown_active = False
            self._btn_play.setEnabled(True)
            self._btn_stop.setEnabled(False)
            self._on_status("Countdown cancelled")
            return
        if self.engine.running and not self.engine.paused:
            self.engine.toggle_pause()
            self._on_status("Paused — press Esc to resume")
            return
        if self.engine.running and self.engine.paused:
            self.engine.toggle_pause()
            return
        self._select_action(-1)

    # ═══════════════════════════════════════════════════════
    #  ADD ACTIONS
    # ═══════════════════════════════════════════════════════

    def add_key_action(self):
        self._add_action(Action(key="w", duration=0.05, action_type="key"))

    def add_pause_action(self):
        self._add_action(Action(key="[DELAY]", duration=0.5, action_type="pause"))

    def add_click_action(self):
        self._add_action(Action(key="[CLICK]", duration=0.05, action_type="click"))

    def add_image_action(self):
        self._add_action(Action(key="[IMAGE]", duration=0.0, action_type="image"))

    def _add_action(self, action: Action):
        self.history.push(self.engine.actions)
        insert_at = self._active_index + 1 if 0 <= self._active_index < len(self.engine.actions) else len(self.engine.actions)
        self.engine.actions.insert(insert_at, action)
        self._refresh_all()
        self._select_action(insert_at)
        self._save_session()

    # ═══════════════════════════════════════════════════════
    #  PROFILE MANAGEMENT
    # ═══════════════════════════════════════════════════════

    def _load_last_session(self):
        session = self.session_manager.load_profile()
        if session:
            try:
                self.engine.actions = [Action.from_dict(x) for x in session.get("actions", [])]
                settings = session.get("settings", {})
                self._spin_loop.setValue(int(settings.get("loops", "1")))
                self._spin_speed.setValue(float(settings.get("speed", 1.0)))
                self._chk_infinite.setChecked(settings.get("infinite_loop", False))
                if "geometry" in settings:
                    self.restoreGeometry(bytes.fromhex(settings["geometry"]))
            except Exception as e:
                logger.error(f"Load session failed: {e}")
        self._refresh_profiles()
        self._refresh_all()
        self._update_statistics()

    def _refresh_profiles(self):
        current = self._profile_combo.currentText()
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for name in self.session_manager.list_profiles():
            self._profile_combo.addItem(name)
        idx = self._profile_combo.findText(self.session_manager.active)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)
        self._profile_combo.blockSignals(False)
        self._update_window_title()

    def _switch_profile(self, name: str):
        self._save_session()
        self.session_manager.switch_profile(name)
        self._load_last_session()
        self._on_status(f"Profile '{name}' loaded")

    def _new_profile(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if ok and name:
            if self.session_manager.new_profile(name):
                self.session_manager.switch_profile(name)
                self.engine.actions = []
                self._refresh_all()
                self._refresh_profiles()
                self._save_session()
            else:
                QMessageBox.warning(self, "Exists", f"Profile '{name}' already exists.")

    def _rename_profile(self):
        from PyQt6.QtWidgets import QInputDialog
        old = self.session_manager.active
        name, ok = QInputDialog.getText(self, "Rename Profile", "New name:", text=old)
        if ok and name and name != old:
            if self.session_manager.rename_profile(old, name):
                self._refresh_profiles()
            else:
                QMessageBox.warning(self, "Error", "Could not rename profile.")

    def _delete_profile(self):
        name = self.session_manager.active
        if name == ProfileManager.DEFAULT_PROFILE:
            QMessageBox.information(self, "Cannot delete", "The default profile cannot be deleted.")
            return
        reply = QMessageBox.question(self, "Delete profile",
            f"Delete profile '{name}'?\nThis cannot be undone.")
        if reply == QMessageBox.StandardButton.Yes:
            self.session_manager.delete_profile(name)
            self._switch_profile(self.session_manager.active)

    # ═══════════════════════════════════════════════════════
    #  SAVE / STATS / REFRESH
    # ═══════════════════════════════════════════════════════

    def _save_session(self):
        if not self.auto_save_enabled:
            return
        if self._save_timer:
            self._save_timer.stop()
        self._save_timer = QTimer.singleShot(500, self._do_save)

    def _do_save(self):
        settings = {
            "loops": str(self._spin_loop.value()),
            "speed": self._spin_speed.value(),
            "infinite_loop": self._chk_infinite.isChecked(),
            "geometry": self.saveGeometry().toHex().data().decode(),
        }
        self.session_manager.save_profile(self.engine.actions, settings)

    def _update_statistics(self):
        total = len(self.engine.actions)
        total_dur = sum(getattr(a, "duration", 0.0) for a in self.engine.actions)
        mins, secs = divmod(int(total_dur), 60)
        ms = int((total_dur - int(total_dur)) * 1000)
        loops = self.engine.loops_completed_count
        self._lbl_stats.setText(
            f"{total} actions | {mins}:{secs:02d}.{ms:03d} | {loops} loops"
        )

    def _refresh_all(self):
        self._action_table.set_actions(self.engine.actions)
        self._timeline.set_actions(self.engine.actions)
        self._update_statistics()

    def _update_window_title(self):
        self.setWindowTitle(f"MacroForge v{VERSION} — {self.session_manager.active}")

    # ═══════════════════════════════════════════════════════
    #  RECORDING
    # ═══════════════════════════════════════════════════════

    def _start_recording(self):
        self._recorder["running"] = True
        self._recorder["paused"] = False
        self._recorder["queue"] = queue.Queue()
        self._recorder["presses"] = {}
        self._recorder["modifiers"] = set()
        self._recorder["last_time"] = time.time()
        self._btn_record.setChecked(True)
        self._btn_record.setText("■  Stop")
        self._btn_play.setEnabled(False)
        self._on_status("Recording... Press F9 to stop")
        self._recorder["thread"] = threading.Thread(target=self._record_poll_loop, daemon=True)
        self._recorder["thread"].start()
        self._poll_rec_queue()
        self._rec_anim = Animator.pulse(self._btn_record, 800)

    def _stop_recording(self):
        self._recorder["running"] = False
        self._recorder["paused"] = False
        self._btn_record.setChecked(False)
        self._btn_record.setText("●  Record")
        self._btn_play.setEnabled(True)
        self._on_status("Recording stopped")
        if self._rec_anim:
            self._rec_anim.stop()
            self._btn_record.setGraphicsEffect(None)

    def _record_poll_loop(self):
        import ctypes
        user32 = ctypes.windll.user32
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
        rec = self._recorder
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

    def _poll_rec_queue(self):
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
                self._refresh_all()
                self._select_action(len(self.engine.actions) - 1)
                self._save_session()
        except Exception as e:
            logger.error(f"_poll_rec_queue: {e}")
        if rec["running"]:
            QTimer.singleShot(50, self._poll_rec_queue)

    def _rec_delete_last(self):
        try:
            if self.engine.actions:
                self.history.push(self.engine.actions)
                self.engine.actions.pop()
                self._refresh_all()
                self._select_action(len(self.engine.actions) - 1)
                self._save_session()
                self._on_status("Deleted last recorded action")
        except Exception as e:
            logger.debug(f"rec_delete_last: {e}")

    # ═══════════════════════════════════════════════════════
    #  DIALOGS
    # ═══════════════════════════════════════════════════════

    def _open_settings(self):
        dlg = SettingsDialog(self, self.settings_manager)
        dlg.exec()

    def _open_logs(self):
        dlg = LogViewerDialog(self)
        dlg.exec()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    # ═══════════════════════════════════════════════════════
    #  IMPORT / EXPORT
    # ═══════════════════════════════════════════════════════

    def export_csv(self):
        if not self.engine.actions:
            QMessageBox.warning(self, "No Actions", "Nothing to export")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "actions.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["index", "key", "duration", "hold", "lane", "rand_delay", "rand_key"])
                for i, a in enumerate(self.engine.actions):
                    writer.writerow([i + 1, a.key, a.duration, a.hold_mode, a.lane, a.random_delay, a.random_key])
            self._on_status(f"Exported {len(self.engine.actions)} actions")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            self.history.push(self.engine.actions)
            new_actions = []
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    a = Action(
                        key=row.get("key", ""),
                        duration=float(row.get("duration", 0.0)),
                        hold_mode=row.get("hold", "").lower() in ("true", "1", "yes"),
                        lane=int(row.get("lane", 0)),
                        random_delay=float(row.get("rand_delay", 0.0)),
                        random_key=row.get("rand_key", "").lower() in ("true", "1", "yes"),
                    )
                    new_actions.append(a)
            self.engine.actions.extend(new_actions)
            self._refresh_all()
            self._save_session()
            self._on_status(f"Imported {len(new_actions)} actions")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def save_json(self):
        if not self.engine.actions:
            QMessageBox.warning(self, "No Actions", "Nothing to export")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export JSON", "actions.json", "JSON (*.json)")
        if not path:
            return
        try:
            import json
            data = {
                "profile": self.session_manager.active,
                "actions": [a.to_dict() for a in self.engine.actions],
                "settings": {
                    "loops": str(self._spin_loop.value()),
                    "speed": self._spin_speed.value(),
                    "infinite_loop": self._chk_infinite.isChecked(),
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._on_status(f"Saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            actions_data = data.get("actions", [])
            self.history.push(self.engine.actions)
            self.engine.actions = [Action.from_dict(x) for x in actions_data]
            self._refresh_all()
            self._save_session()
            self._on_status(f"Imported {len(self.engine.actions)} actions from JSON")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    # ═══════════════════════════════════════════════════════
    #  UPDATE CHECKING
    # ═══════════════════════════════════════════════════════

    def _check_update_silent(self):
        def _bg():
            from updater import check_update
            manifest = check_update(silent=True)
            if manifest:
                self._pending_update = manifest
                self._on_status("Update available — check Settings menu")
        threading.Thread(target=_bg, daemon=True).start()

    def _check_update_manual(self):
        from updater import check_update, perform_update
        self._on_status("Checking for updates...")
        def _bg():
            manifest = check_update(silent=False)
            if manifest:
                self._pending_update = manifest
                self._show_update_dialog(manifest)
            else:
                self._on_status("No updates available")
        threading.Thread(target=_bg, daemon=True).start()

    def _show_update_dialog(self, manifest):
        remote_ver = manifest.get("version", "unknown")
        notes = manifest.get("notes", "")
        msg = f"A new version of MacroForge is available.\n\nCurrent: {VERSION}\nLatest: {remote_ver}"
        if notes:
            msg += f"\n\nRelease notes:\n{notes}"
        reply = QMessageBox.question(self, "Update Available", msg + "\n\nDownload and install now?")
        if reply == QMessageBox.StandardButton.Yes:
            self._on_status("Downloading update...")
            def _download():
                try:
                    if perform_update(manifest):
                        self._on_status("Update installed — restarting...")
                        QTimer.singleShot(1000, self.close)
                    else:
                        self._on_status("Update failed")
                except Exception as e:
                    logger.error(f"Update download error: {e}")
                    self._on_status("Update failed")
            threading.Thread(target=_download, daemon=True).start()

    # ═══════════════════════════════════════════════════════
    #  LIFECYCLE
    # ═══════════════════════════════════════════════════════

    def closeEvent(self, event):
        self._save_session()
        self.engine.running = False
        if hasattr(self, '_tray') and self._tray:
            self._tray.hide()
        event.accept()
