"""Tests for the playback controller module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch

from ui.playback_controller import PlaybackController, create_playback_controller


class TestPlaybackController(unittest.TestCase):
    """Test cases for PlaybackController."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.window = MagicMock()
        self.controller = PlaybackController(self.window)
        
        # Mock engine
        self.engine = MagicMock()
        self.engine.running = False
        self.engine.paused = False
        self.engine.actions = []
        self.controller.set_engine(self.engine)
        
        # Mock callbacks
        self.feedback_cb = MagicMock()
        self.status_cb = MagicMock()
        self.controller.set_callbacks(self.feedback_cb, self.status_cb)
    
    def test_initial_state(self):
        """Test initial controller state."""
        self.assertEqual(self.controller.actions_played, 0)
        self.assertEqual(self.controller.session_elapsed_time, 0.0)
        self.assertIsNone(self.controller.session_start_time)
        self.assertFalse(self.controller.is_running())
        self.assertFalse(self.controller.is_paused())
    
    def test_start_no_engine(self):
        """Test start without engine set."""
        controller = PlaybackController(self.window)
        controller.set_callbacks(self.feedback_cb, self.status_cb)
        result = controller.start()
        
        self.assertFalse(result)
        self.status_cb.assert_called_with("No engine set")
    
    def test_start_already_running(self):
        """Test start when already running."""
        self.engine.running = True
        
        result = self.controller.start()
        
        self.assertFalse(result)
        self.status_cb.assert_called_with("Already running")
    
    def test_start_empty_actions(self):
        """Test start with empty actions."""
        self.engine.actions = []
        
        result = self.controller.start()
        
        self.assertFalse(result)
        self.status_cb.assert_called_with("No actions to run")
    
    def test_start_success(self):
        """Test successful start."""
        self.engine.actions = [MagicMock(), MagicMock()]
        
        result = self.controller.start()
        
        self.assertTrue(result)
        self.engine.start.assert_called_once()
        self.assertIsNotNone(self.controller.session_start_time)
        self.feedback_cb.assert_called_with("Starting macro…")
    
    def test_stop(self):
        """Test stop."""
        self.controller.start()
        self.controller.stop()
        
        self.engine.stop.assert_called_once()
        self.assertEqual(self.controller.session_start_time, None)
    
    def test_pause_toggle(self):
        """Test pause toggle."""
        self.engine.running = True
        self.engine.paused = False
        
        self.controller.pause()
        
        self.engine.toggle_pause.assert_called_once()
    
    def test_increment_actions_played(self):
        """Test incrementing actions played counter."""
        self.controller.increment_actions_played()
        self.assertEqual(self.controller.actions_played, 1)
        
        self.controller.increment_actions_played()
        self.assertEqual(self.controller.actions_played, 2)
    
    def test_get_elapsed_time_not_running(self):
        """Test getting elapsed time when not running."""
        self.controller.session_elapsed_time = 10.0
        
        elapsed = self.controller.get_elapsed_time()
        
        self.assertEqual(elapsed, 10.0)
    
    def test_is_single_test(self):
        """Test single test flag."""
        self.assertFalse(self.controller.is_single_test())
        
        self.controller.test_action(MagicMock(), 0)
        self.assertTrue(self.controller.is_single_test())
    
    def test_update_progress(self):
        """Test progress update."""
        self.controller.update_progress(0.5)
        
        self.window.progress_bar.setValue.assert_called_with(50)
        self.window.progress_label.setText.assert_called_with("50%")


class TestCreatePlaybackController(unittest.TestCase):
    """Test cases for the factory function."""
    
    def test_factory_creates_controller(self):
        """Test that factory creates a PlaybackController."""
        window = MagicMock()
        
        controller = create_playback_controller(window)
        
        self.assertIsInstance(controller, PlaybackController)
        self.assertEqual(controller.window, window)


if __name__ == "__main__":
    unittest.main()
