"""Tests for the toolbar controller module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from ui.toolbar_controller import ToolbarController, create_toolbar_controller


class TestToolbarController(unittest.TestCase):
    """Test cases for ToolbarController."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.window = MagicMock()
        self.window.session_manager = MagicMock()
        self.window.session_manager.active = "TestProfile"
        self.controller = ToolbarController(self.window)
    
    def test_initial_state(self):
        """Test initial controller state."""
        self.assertEqual(self.controller._toolbar_profile_mode, "full")
        self.assertEqual(self.controller._toolbar_profile_full_width, 164)
        self.assertEqual(self.controller._toolbar_profile_compact_width, 132)
        self.assertEqual(self.controller._toolbar_profile_tiny_width, 116)
    
    def test_toolbar_profile_text_full_mode(self):
        """Test profile text in full mode."""
        self.controller._toolbar_profile_mode = "full"
        text = self.controller._toolbar_profile_text()
        
        self.assertIn("TestProfile", text)
        self.assertIn("▾", text)
    
    def test_toolbar_profile_text_tiny_mode(self):
        """Test profile text in tiny mode with truncation."""
        self.controller._toolbar_profile_mode = "tiny"
        self.window.session_manager.active = "VeryLongProfileName"
        
        text = self.controller._toolbar_profile_text()
        
        # Should be truncated
        self.assertIn("…", text)
        self.assertLess(len(text), 25)
    
    def test_toolbar_profile_text_compact_mode(self):
        """Test profile text in compact mode."""
        self.controller._toolbar_profile_mode = "compact"
        text = self.controller._toolbar_profile_text()
        
        self.assertIn("TestProfile", text)
    
    def test_update_selection_chip_visible(self):
        """Test selection chip visibility with count."""
        self.controller.update_selection_chip(5)
        
        self.window.selection_chip.setVisible.assert_called_with(True)
        self.window.selection_count_label.setText.assert_called_with("5 selected")
    
    def test_update_selection_chip_hidden(self):
        """Test selection chip hidden with zero count."""
        self.controller.update_selection_chip(0)
        
        self.window.selection_chip.setVisible.assert_called_with(False)
    
    def test_update_playback_buttons_running(self):
        """Test playback buttons when running."""
        self.controller.update_playback_buttons(running=True, paused=False)
        
        self.window.start_btn.setEnabled.assert_called_with(False)
        self.window.pause_btn.setEnabled.assert_called_with(True)
        self.window.stop_btn.setEnabled.assert_called_with(True)
    
    def test_update_playback_buttons_stopped(self):
        """Test playback buttons when stopped."""
        self.controller.update_playback_buttons(running=False, paused=False)
        
        self.window.start_btn.setEnabled.assert_called_with(True)
    
    def test_update_profile_button(self):
        """Test profile button update."""
        self.controller.update_profile_button()
        
        self.window.profile_btn.setText.assert_called()


class TestCreateToolbarController(unittest.TestCase):
    """Test cases for the factory function."""
    
    def test_factory_creates_controller(self):
        """Test that factory creates a ToolbarController."""
        window = MagicMock()
        
        controller = create_toolbar_controller(window)
        
        self.assertIsInstance(controller, ToolbarController)
        self.assertEqual(controller.window, window)


if __name__ == "__main__":
    unittest.main()
