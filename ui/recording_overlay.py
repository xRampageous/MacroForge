"""Recording overlay and improvements for MacroForge.

Provides visual recording indicator and post-recording edit dialog.
"""

import time
from typing import Optional, List, Callable

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QRect
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QCheckBox, QSpinBox, QDoubleSpinBox,
    QDialogButtonBox, QWidget
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QFontMetrics

from ui.theme import COLORS
from debugger import logger


class RecordingOverlay(QFrame):
    """Floating overlay showing recording status.
    
    Displays:
    - Recording indicator (red pulsing circle)
    - Duration timer
    - Action count
    - Pause/Stop buttons
    """
    
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self._recording = False
        self._paused = False
        self._start_time = 0.0
        self._action_count = 0
        
        self._setup_ui()
        self._setup_animation()
        
        # Position in top-right corner
        self._position_overlay()
    
    def _setup_ui(self):
        """Set up the overlay UI."""
        self.setFixedSize(220, 100)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
        # Status row
        status_layout = QHBoxLayout()
        
        # Recording indicator (pulsing circle)
        self._indicator = QLabel("⬤")
        self._indicator.setStyleSheet("color: #ef4444; font-size: 14px;")
        status_layout.addWidget(self._indicator)
        
        # Recording text
        self._status_label = QLabel("RECORDING")
        self._status_label.setStyleSheet(f"""
            color: {COLORS['text']};
            font-weight: 800;
            font-size: 12px;
        """)
        status_layout.addWidget(self._status_label)
        
        status_layout.addStretch()
        
        # Duration
        self._time_label = QLabel("00:00")
        self._time_label.setStyleSheet(f"""
            color: {COLORS['accent']};
            font-family: Consolas;
            font-weight: 700;
            font-size: 14px;
        """)
        status_layout.addWidget(self._time_label)
        
        layout.addLayout(status_layout)
        
        # Stats row
        stats_layout = QHBoxLayout()
        
        self._actions_label = QLabel("0 actions")
        self._actions_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        stats_layout.addWidget(self._actions_label)
        
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self._pause_btn = QPushButton("⏸ Pause")
        self._pause_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 10px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
            }}
        """)
        self._pause_btn.clicked.connect(self._on_pause)
        btn_layout.addWidget(self._pause_btn)
        
        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: 700;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
            }}
        """)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self._stop_btn)
        
        layout.addLayout(btn_layout)
        
        # Background styling
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg']};
                border: 2px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
    
    def _setup_animation(self):
        """Set up pulsing animation timer."""
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start(500)  # Pulse every 500ms
        
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_time)
        self._update_timer.start(100)  # Update time every 100ms
        
        self._pulse_state = False
    
    def _position_overlay(self):
        """Position overlay in top-right of screen."""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(geo.width() - 240, 20)
    
    def _pulse(self):
        """Pulse the recording indicator."""
        if not self._paused:
            self._pulse_state = not self._pulse_state
            opacity = "1.0" if self._pulse_state else "0.5"
            self._indicator.setStyleSheet(f"color: #ef4444; font-size: 14px; opacity: {opacity};")
    
    def _update_time(self):
        """Update the duration display."""
        if self._recording and not self._paused:
            elapsed = time.time() - self._start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            self._time_label.setText(f"{minutes:02d}:{seconds:02d}")
    
    def _on_pause(self):
        """Handle pause button click."""
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.setText("▶ Resume")
            self._status_label.setText("PAUSED")
            self._indicator.setStyleSheet("color: #fbbf24; font-size: 14px;")
        else:
            self._pause_btn.setText("⏸ Pause")
            self._status_label.setText("RECORDING")
            self._indicator.setStyleSheet("color: #ef4444; font-size: 14px;")
        
        self.pause_clicked.emit()
    
    def _on_stop(self):
        """Handle stop button click."""
        self._recording = False
        self._update_timer.stop()
        self._pulse_timer.stop()
        self.hide()
        self.stop_clicked.emit()
    
    def start_recording(self):
        """Start recording display."""
        self._recording = True
        self._paused = False
        self._start_time = time.time()
        self._action_count = 0
        self._actions_label.setText("0 actions")
        self.show()
    
    def increment_action_count(self):
        """Increment the recorded action count."""
        self._action_count += 1
        self._actions_label.setText(f"{self._action_count} action{'s' if self._action_count != 1 else ''}")
    
    def get_elapsed_time(self) -> float:
        """Get elapsed recording time."""
        if not self._recording:
            return 0.0
        return time.time() - self._start_time


class PostRecordingDialog(QDialog):
    """Post-recording edit dialog.
    
    Allows users to:
    - Review recorded actions
    - Edit timings
    - Merge consecutive keys into holds
    - Delete unwanted actions
    - Rename/categorize
    """
    
    actions_accepted = pyqtSignal(list)  # List of edited actions
    
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        
        self._original_actions = actions
        self._edited_actions = [self._action_to_row_data(a) for a in actions]
        
        self.setWindowTitle("Review Recorded Actions")
        self.setMinimumSize(700, 500)
        
        self._setup_ui()
    
    def _action_to_row_data(self, action):
        """Convert action to editable row data."""
        return {
            'enabled': True,
            'type': getattr(action, 'action_type', 'key'),
            'key': getattr(action, 'key', ''),
            'duration': getattr(action, 'duration', 0.1),
            'original': action
        }
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(f"Review {len(self._original_actions)} Recorded Actions")
        header.setStyleSheet(f"""
            color: {COLORS['text']};
            font-size: 16px;
            font-weight: 700;
        """)
        layout.addWidget(header)
        
        # Description
        desc = QLabel("Edit timings, disable unwanted actions, or merge consecutive key presses into holds.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        layout.addWidget(desc)
        
        # Quick actions
        quick_layout = QHBoxLayout()
        
        merge_btn = QPushButton("Merge Consecutive Keys")
        merge_btn.setToolTip("Convert consecutive key presses into hold actions")
        merge_btn.clicked.connect(self._merge_consecutive)
        quick_layout.addWidget(merge_btn)
        
        remove_short = QPushButton("Remove Short Pauses")
        remove_short.setToolTip("Remove pauses shorter than 0.1s")
        remove_short.clicked.connect(self._remove_short_pauses)
        quick_layout.addWidget(remove_short)
        
        quick_layout.addStretch()
        
        layout.addLayout(quick_layout)
        
        # Actions table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["", "Type", "Key/Action", "Duration", "Actions"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(3, 80)
        self._table.setColumnWidth(4, 100)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        self._populate_table()
        
        layout.addWidget(self._table)
        
        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        
        # Customize button text
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Add to Timeline")
        
        layout.addWidget(btn_box)
    
    def _populate_table(self):
        """Populate the actions table."""
        self._table.setRowCount(len(self._edited_actions))
        
        for row, data in enumerate(self._edited_actions):
            # Enabled checkbox
            chk = QCheckBox()
            chk.setChecked(data['enabled'])
            chk.stateChanged.connect(lambda state, r=row: self._on_enabled_changed(r, state))
            self._table.setCellWidget(row, 0, chk)
            
            # Type
            type_item = QTableWidgetItem(data['type'].upper())
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 1, type_item)
            
            # Key/Action
            key_text = data['key'] if data['type'] == 'key' else f"[{data['type']}]"
            key_item = QTableWidgetItem(key_text)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 2, key_item)
            
            # Duration
            duration_spin = QDoubleSpinBox()
            duration_spin.setRange(0.01, 60.0)
            duration_spin.setSingleStep(0.1)
            duration_spin.setDecimals(2)
            duration_spin.setValue(data['duration'])
            duration_spin.valueChanged.connect(lambda v, r=row: self._on_duration_changed(r, v))
            self._table.setCellWidget(row, 3, duration_spin)
            
            # Actions buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 0, 4, 0)
            actions_layout.setSpacing(4)
            
            delete_btn = QPushButton("🗑")
            delete_btn.setFixedSize(24, 24)
            delete_btn.setToolTip("Delete this action")
            delete_btn.clicked.connect(lambda _, r=row: self._delete_row(r))
            actions_layout.addWidget(delete_btn)
            
            self._table.setCellWidget(row, 4, actions_widget)
    
    def _on_enabled_changed(self, row, state):
        """Handle enable checkbox change."""
        if 0 <= row < len(self._edited_actions):
            self._edited_actions[row]['enabled'] = bool(state)
    
    def _on_duration_changed(self, row, value):
        """Handle duration change."""
        if 0 <= row < len(self._edited_actions):
            self._edited_actions[row]['duration'] = value
    
    def _delete_row(self, row):
        """Delete a row from the table."""
        if 0 <= row < len(self._edited_actions):
            del self._edited_actions[row]
            self._table.removeRow(row)
    
    def _merge_consecutive(self):
        """Merge consecutive key presses into hold actions."""
        # Implementation would detect consecutive key presses
        # and convert them to hold actions with appropriate duration
        logger.info("Merge consecutive keys not yet implemented")
    
    def _remove_short_pauses(self):
        """Remove pauses shorter than threshold."""
        threshold = 0.1
        to_remove = []
        
        for i, data in enumerate(self._edited_actions):
            if data['type'] == 'pause' and data['duration'] < threshold:
                to_remove.append(i)
        
        # Remove in reverse order to maintain indices
        for i in reversed(to_remove):
            self._delete_row(i)
    
    def _accept(self):
        """Accept the edited actions."""
        # Build list of enabled actions
        enabled_actions = []
        for data in self._edited_actions:
            if data['enabled']:
                action = data['original']
                # Apply edits
                action.duration = data['duration']
                enabled_actions.append(action)
        
        self.actions_accepted.emit(enabled_actions)
        self.accept()


def show_recording_overlay(parent=None) -> RecordingOverlay:
    """Create and show the recording overlay."""
    overlay = RecordingOverlay(parent)
    return overlay


def show_post_recording_dialog(actions, parent=None) -> PostRecordingDialog:
    """Show the post-recording edit dialog."""
    dlg = PostRecordingDialog(actions, parent)
    return dlg
