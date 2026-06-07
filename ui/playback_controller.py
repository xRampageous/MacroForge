"""Playback controller for MacroForge.

Manages playback state, button controls, progress bar, status dot, and feedback.
"""

import time
from typing import Optional, Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QProgressBar, QLabel, QPushButton

from ui.theme import COLORS
from ui.status_dot import StatusDot
from debugger import logger


class PlaybackController:
    """Manages macro playback state and UI feedback.
    
    This class handles:
    - Playback state (running, paused, stopped)
    - Playback button states (start, pause, stop)
    - Progress bar updates
    - Status dot color changes
    - Playback feedback messages
    - Session timing statistics
    """
    
    def __init__(self, window):
        self.window = window
        self._feedback_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
        
        # Playback statistics
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time: Optional[float] = None
        self._seq_dur_cache = 0.0
        
        # Single test tracking
        self._single_test_active = False
        self._single_test_index = -1
        
        # Reference to engine (set externally)
        self.engine = None
    
    def set_engine(self, engine):
        """Set the execution engine reference."""
        self.engine = engine
    
    def set_callbacks(self, feedback_cb: Callable, status_cb: Callable):
        """Set callback functions for feedback and status updates."""
        self._feedback_callback = feedback_cb
        self._status_callback = status_cb
    
    # ═══════════════════════════════════════════════════════
    #  PLAYBACK CONTROL
    # ═══════════════════════════════════════════════════════
    
    def start(self, actions=None, loops=1, infinite=False, 
              capture_focus=False, run_from_index=0):
        """Start macro playback.
        
        Args:
            actions: List of actions to play (uses engine.actions if None)
            loops: Number of loops to run
            infinite: Run until stopped
            capture_focus: Capture focus window at start
            run_from_index: Start from specific action index
        """
        if not self.engine:
            logger.error("Cannot start: no engine set")
            self._status("No engine set")
            return False
        
        if self.engine.running:
            self._status("Already running")
            return False
        
        # Update engine actions if provided
        if actions is not None:
            self.engine.actions = actions
        
        # Check for empty action list
        if not self.engine.actions:
            self._status("No actions to run")
            return False
        
        # Reset statistics
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        
        # Update UI state
        self._set_buttons_running()
        self._set_status_dot("playing")
        self._set_progress(0)
        self._feedback("Starting macro…")
        
        # Sync engine options
        self.engine.loops = loops if not infinite else 1
        self.engine.infinite_loop = infinite
        
        if capture_focus:
            self.engine.capture_focus_window()
        
        # Start engine
        self.engine.start()
        return True
    
    def stop(self):
        """Stop macro playback."""
        if not self.engine:
            return
        
        self._single_test_active = False
        self._single_test_index = -1
        
        self.engine.stop()
        
        # Update UI state
        self._set_buttons_stopped()
        self._set_status_dot("idle")
        self._set_progress(0)
        self._feedback("Stopped")
        
        # Update session time
        if self.session_start_time:
            self.session_elapsed_time += time.time() - self.session_start_time
            self.session_start_time = None
    
    def pause(self):
        """Toggle pause state."""
        if not self.engine:
            return
        
        if not self.engine.running:
            return
        
        self.engine.toggle_pause()
        
        if self.engine.paused:
            self._set_status_dot("paused")
            self._feedback("Paused")
            if self.session_start_time:
                self.session_elapsed_time += time.time() - self.session_start_time
                self.session_start_time = None
        else:
            self._set_status_dot("playing")
            self._feedback("Resumed")
            self.session_start_time = time.time()
    
    def test_action(self, action, index=0):
        """Test a single action."""
        if not self.engine:
            return False
        
        if self.engine.running:
            self._status("Stop playback before testing")
            return False
        
        self._single_test_active = True
        self._single_test_index = index
        
        # Reset statistics
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        
        # Set single action
        self.engine.actions = [action]
        
        # Update UI
        self._set_buttons_running()
        self._set_status_dot("playing")
        self._set_progress(0)
        self._feedback(f"Testing row {index + 1}")
        
        self.engine.start()
        return True
    
    def test_from_row(self, index, actions):
        """Test from a specific row to end."""
        if not self.engine:
            return False
        
        if self.engine.running:
            self._status("Stop playback before testing")
            return False
        
        self._single_test_active = False
        self._single_test_index = -1
        
        # Reset statistics
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        
        # Set actions from index
        self.engine.actions = actions[index:]
        
        # Update UI
        self._set_buttons_running()
        self._set_status_dot("playing")
        self._set_progress(0)
        self._feedback(f"Testing from row {index + 1}")
        
        self.engine.start()
        return True
    
    def run_selected_actions(self, actions, rows, infinite=False, loops=1, capture_focus=True):
        """Run a selected block of actions.
        
        Args:
            actions: List of actions to run
            rows: List of row indices (for display/logging)
            infinite: Run in infinite loop
            loops: Number of loops (ignored if infinite=True)
            capture_focus: Capture focus window at start
        
        Returns:
            True if started successfully, False otherwise
        """
        if not self.engine:
            self._status("No engine set")
            return False
        
        if self.engine.running:
            self._status("Stop playback before running selected block")
            return False
        
        if not actions:
            self._status("No actions to run")
            return False
        
        # Reset statistics
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = time.time()
        
        # Set actions
        self.engine.actions = actions
        
        # Update UI state
        self._set_buttons_running()
        self._set_status_dot("playing")
        self._set_progress(0)
        self._feedback("Running selected block")
        
        # Sync engine options
        self.engine.loops = 1 if infinite else loops
        self.engine.infinite_loop = infinite
        
        if capture_focus:
            self.engine.capture_focus_window()
        
        # Start engine
        self.engine.start()
        
        # Log
        row_str = ', '.join(str(r + 1) for r in rows)
        logger.info(f"[PLAY] Running selected block: rows {row_str}")
        
        return True
    
    # ═══════════════════════════════════════════════════════
    #  UI UPDATES
    # ═══════════════════════════════════════════════════════
    
    def _set_buttons_running(self):
        """Set button states for running."""
        try:
            if hasattr(self.window, 'start_btn'):
                self.window.start_btn.setEnabled(False)
            if hasattr(self.window, 'pause_btn'):
                self.window.pause_btn.setEnabled(True)
                self.window.pause_btn.setChecked(False)
            if hasattr(self.window, 'stop_btn'):
                self.window.stop_btn.setEnabled(True)
        except Exception as e:
            logger.debug(f"Button update error: {e}")
    
    def _set_buttons_stopped(self):
        """Set button states for stopped."""
        try:
            if hasattr(self.window, 'start_btn'):
                self.window.start_btn.setEnabled(True)
            if hasattr(self.window, 'pause_btn'):
                self.window.pause_btn.setEnabled(False)
                self.window.pause_btn.setChecked(False)
            if hasattr(self.window, 'stop_btn'):
                self.window.stop_btn.setEnabled(False)
        except Exception as e:
            logger.debug(f"Button update error: {e}")
    
    def _set_buttons_paused(self):
        """Set button states for paused."""
        try:
            if hasattr(self.window, 'pause_btn'):
                self.window.pause_btn.setChecked(True)
        except Exception as e:
            logger.debug(f"Button update error: {e}")
    
    def _set_status_dot(self, state: str):
        """Set status dot color and glow.
        
        Args:
            state: One of 'playing', 'paused', 'idle', 'recording'
        """
        try:
            status_dot = getattr(self.window, 'status_dot', None)
            if not status_dot:
                return
            
            colors = {
                'playing': (COLORS.get('playing', '#22d3ee'), True),
                'paused': (COLORS.get('pause_cyan', '#0ea5e9'), False),
                'idle': (COLORS.get('text_dark', '#64748b'), False),
                'recording': (COLORS.get('recording', '#ef4444'), True),
            }
            color, glow = colors.get(state, (COLORS.get('text_dark', '#64748b'), False))
            status_dot.set_color(color, glow=glow)
        except Exception as e:
            logger.debug(f"Status dot update error: {e}")
    
    def _set_progress(self, value: float):
        """Set progress bar value (0-100)."""
        try:
            progress_bar = getattr(self.window, 'progress_bar', None)
            progress_label = getattr(self.window, 'progress_label', None)
            
            if progress_bar:
                progress_bar.setValue(int(value))
            if progress_label:
                progress_label.setText(f"{int(value)}%")
        except Exception as e:
            logger.debug(f"Progress update error: {e}")
    
    def update_progress(self, progress: float):
        """Update progress from engine callback."""
        self._set_progress(progress * 100)
    
    def _feedback(self, msg: str):
        """Send feedback message."""
        if self._feedback_callback:
            self._feedback_callback(msg)
    
    def _status(self, msg: str):
        """Send status message."""
        if self._status_callback:
            self._status_callback(msg)
    
    # ═══════════════════════════════════════════════════════
    #  STATISTICS
    # ═══════════════════════════════════════════════════════
    
    def get_elapsed_time(self) -> float:
        """Get total elapsed time including current session."""
        total = self.session_elapsed_time
        if self.session_start_time:
            total += time.time() - self.session_start_time
        return total
    
    def reset_statistics(self):
        """Reset all playback statistics."""
        self.actions_played = 0
        self.session_elapsed_time = 0.0
        self.session_start_time = None
    
    def increment_actions_played(self):
        """Increment the actions played counter."""
        self.actions_played += 1
    
    def is_running(self) -> bool:
        """Check if playback is running."""
        return self.engine.running if self.engine else False
    
    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self.engine.paused if self.engine else False
    
    def is_single_test(self) -> bool:
        """Check if currently running a single action test."""
        return self._single_test_active


def create_playback_controller(window) -> PlaybackController:
    """Factory function to create a PlaybackController."""
    return PlaybackController(window)
