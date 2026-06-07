"""Tests for recording overlay functionality."""

import unittest
from unittest.mock import MagicMock, patch
import time

import sys
sys.path.insert(0, r'C:\Users\Andie\MacroForge')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.recording_overlay import RecordingOverlay, PostRecordingDialog


# Create QApplication for tests
_app = QApplication.instance() or QApplication([])


class TestRecordingOverlay(unittest.TestCase):
    """Test cases for RecordingOverlay."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.overlay = RecordingOverlay()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.overlay.hide()
        self.overlay.deleteLater()
    
    def test_initial_state(self):
        """Test overlay initial state."""
        self.assertFalse(self.overlay._recording)
        self.assertFalse(self.overlay._paused)
        self.assertEqual(self.overlay._action_count, 0)
        self.assertEqual(self.overlay._start_time, 0.0)
    
    def test_start_recording(self):
        """Test starting recording."""
        self.overlay.start_recording()
        
        self.assertTrue(self.overlay._recording)
        self.assertFalse(self.overlay._paused)
        self.assertGreater(self.overlay._start_time, 0)
        self.assertEqual(self.overlay._action_count, 0)
        self.assertEqual(self.overlay._actions_label.text(), "0 actions")
    
    def test_increment_action_count(self):
        """Test incrementing action count."""
        self.overlay.start_recording()
        
        self.overlay.increment_action_count()
        self.assertEqual(self.overlay._action_count, 1)
        self.assertEqual(self.overlay._actions_label.text(), "1 action")
        
        self.overlay.increment_action_count()
        self.assertEqual(self.overlay._action_count, 2)
        self.assertEqual(self.overlay._actions_label.text(), "2 actions")
    
    def test_pause_resume(self):
        """Test pause and resume functionality."""
        self.overlay.start_recording()
        
        # Initial state
        self.assertFalse(self.overlay._paused)
        
        # Simulate pause button click
        self.overlay._on_pause()
        
        self.assertTrue(self.overlay._paused)
        self.assertEqual(self.overlay._status_label.text(), "PAUSED")
        
        # Simulate resume
        self.overlay._on_pause()
        
        self.assertFalse(self.overlay._paused)
        self.assertEqual(self.overlay._status_label.text(), "RECORDING")
    
    def test_stop_recording(self):
        """Test stopping recording."""
        self.overlay.start_recording()
        self.overlay.increment_action_count()
        
        # Simulate stop button click
        self.overlay._on_stop()
        
        self.assertFalse(self.overlay._recording)
    
    def test_get_elapsed_time(self):
        """Test elapsed time calculation."""
        # Before recording starts
        self.assertEqual(self.overlay.get_elapsed_time(), 0.0)
        
        # After recording starts
        self.overlay.start_recording()
        time.sleep(0.1)  # Small delay
        elapsed = self.overlay.get_elapsed_time()
        self.assertGreater(elapsed, 0)
    
    def test_time_display_format(self):
        """Test time label display format."""
        self.overlay._start_time = time.time() - 65  # 1 minute 5 seconds ago
        self.overlay._update_time()
        
        # Should display "01:05"
        self.assertEqual(self.overlay._time_label.text(), "01:05")
    
    def test_signals_emitted(self):
        """Test that signals are emitted correctly."""
        pause_mock = MagicMock()
        stop_mock = MagicMock()
        
        self.overlay.pause_clicked.connect(pause_mock)
        self.overlay.stop_clicked.connect(stop_mock)
        
        self.overlay._on_pause()
        pause_mock.assert_called_once()
        
        self.overlay._on_stop()
        stop_mock.assert_called_once()


class TestPostRecordingDialog(unittest.TestCase):
    """Test cases for PostRecordingDialog."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock actions
        self.mock_actions = [
            MagicMock(action_type='key', key='a', duration=0.1),
            MagicMock(action_type='pause', duration=0.5),
            MagicMock(action_type='key', key='b', duration=0.2),
        ]
        self.dialog = PostRecordingDialog(self.mock_actions)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.dialog.close()
        self.dialog.deleteLater()
    
    def test_dialog_initialization(self):
        """Test dialog initializes correctly."""
        self.assertEqual(len(self.dialog._original_actions), 3)
        self.assertEqual(len(self.dialog._edited_actions), 3)
    
    def test_action_to_row_data(self):
        """Test conversion of action to row data."""
        action = MagicMock(action_type='key', key='x', duration=0.3)
        row_data = self.dialog._action_to_row_data(action)
        
        self.assertEqual(row_data['type'], 'key')
        self.assertEqual(row_data['key'], 'x')
        self.assertEqual(row_data['duration'], 0.3)
        self.assertTrue(row_data['enabled'])
    
    def test_remove_short_pauses(self):
        """Test removing short pauses."""
        # Add a short pause
        short_pause = MagicMock(action_type='pause', duration=0.05)
        self.dialog._original_actions.append(short_pause)
        self.dialog._edited_actions.append(self.dialog._action_to_row_data(short_pause))
        
        initial_count = len(self.dialog._edited_actions)
        self.dialog._remove_short_pauses()
        
        # Should have removed the short pause
        self.assertLess(len(self.dialog._edited_actions), initial_count)


if __name__ == '__main__':
    unittest.main()
