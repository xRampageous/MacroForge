"""Tests for the inspector controller module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch, call

from ui.inspector_controller import InspectorController, create_inspector_controller


class FakeSignal:
    """Small signal stand-in for controller unit tests."""

    def __init__(self):
        self.connect = MagicMock()


class FakeTimer:
    """Timer stand-in with the QTimer methods InspectorController uses."""

    def __init__(self, parent=None):
        self.parent = parent
        self.timeout = FakeSignal()
        self.setSingleShot = MagicMock()
        self.setInterval = MagicMock()
        self.start = MagicMock()


class TestInspectorController(unittest.TestCase):
    """Test cases for InspectorController."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.window = MagicMock()
        self.controller = InspectorController(self.window, timer_factory=FakeTimer)
    
    def test_initial_state(self):
        """Test initial controller state."""
        self.assertFalse(self.controller.is_loading())
        self.assertIsNotNone(self.controller._inspector_autosave_timer)
    
    def test_set_loading(self):
        """Test setting loading state."""
        self.controller.set_loading(True)
        self.assertTrue(self.controller.is_loading())
        
        self.controller.set_loading(False)
        self.assertFalse(self.controller.is_loading())
    
    def test_show_inspector_key_type(self):
        """Test showing inspector for key action type."""
        self.controller.show_inspector(show=True, action_type="key")
        
        # Key type should use index 0
        self.window.inspector_stack.setCurrentIndex.assert_called_with(0)
    
    def test_show_inspector_image_type(self):
        """Test showing inspector for image action type."""
        self.controller.show_inspector(show=True, action_type="image")
        
        # Image type should use index 2
        self.window.inspector_stack.setCurrentIndex.assert_called_with(2)
    
    def test_show_inspector_group_type(self):
        """Test showing inspector for group action type."""
        self.controller.show_inspector(show=True, action_type="group")
        
        # Group type should use index 4
        self.window.inspector_stack.setCurrentIndex.assert_called_with(4)
    
    def test_show_inspector_unknown_type(self):
        """Test showing inspector for unknown action type."""
        self.controller.show_inspector(show=True, action_type="unknown")
        
        # Unknown type should default to index 0
        self.window.inspector_stack.setCurrentIndex.assert_called_with(0)
    
    def test_show_inspector_hide(self):
        """Test hiding inspector."""
        self.controller.show_inspector(show=False, action_type="key")
        
        # When show=False, should still set index but with 0
        self.window.inspector_stack.setCurrentIndex.assert_called_with(0)
    
    def test_queue_inspector_autosave_when_loading(self):
        """Test that autosave is not queued when loading."""
        self.controller.set_loading(True)
        
        self.controller.queue_inspector_autosave()
        
        # Timer should not be started while loading
        self.controller._inspector_autosave_timer.start.assert_not_called()
    
    def test_queue_inspector_autosave_when_not_loading(self):
        """Test that autosave is queued when not loading."""
        self.controller.set_loading(False)
        self.window.active_index = 0
        self.window.action_model.rowCount.return_value = 5
        
        self.controller.queue_inspector_autosave()
        
        # Timer should be started
        self.controller._inspector_autosave_timer.start.assert_called_once()


class TestCreateInspectorController(unittest.TestCase):
    """Test cases for the factory function."""
    
    def test_factory_creates_controller(self):
        """Test that factory creates an InspectorController."""
        window = MagicMock()
        
        controller = create_inspector_controller(window, timer_factory=FakeTimer)
        
        self.assertIsInstance(controller, InspectorController)
        self.assertEqual(controller.window, window)
    
    def test_factory_sets_up_timer(self):
        """Test that factory sets up the autosave timer."""
        window = MagicMock()
        
        controller = create_inspector_controller(window, timer_factory=FakeTimer)
        
        self.assertIsNotNone(controller._inspector_autosave_timer)


if __name__ == "__main__":
    unittest.main()
