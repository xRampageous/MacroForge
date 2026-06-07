"""Tests for the hotkey manager module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch

from ui.hotkey_manager import HotkeyManager, create_hotkey_manager


class TestHotkeyManager(unittest.TestCase):
    """Test cases for HotkeyManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.window = MagicMock()
        self.settings_manager = MagicMock()
        self.settings_manager.settings = {}
    
    def test_default_hotkeys_loaded(self):
        """Test that default hotkeys are loaded on initialization."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        # Check that default hotkeys exist
        self.assertEqual(mgr.get_hotkey("undo"), "Ctrl+Z")
        self.assertEqual(mgr.get_hotkey("save"), "Ctrl+S")
        self.assertEqual(mgr.get_hotkey("play_pause"), "Space")
    
    def test_custom_hotkey_overrides_default(self):
        """Test that saved hotkeys override defaults."""
        self.settings_manager.settings = {
            "hotkeys": {"undo": "Ctrl+Shift+Z"}
        }
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        self.assertEqual(mgr.get_hotkey("undo"), "Ctrl+Shift+Z")
        # Other hotkeys should still be defaults
        self.assertEqual(mgr.get_hotkey("save"), "Ctrl+S")
    
    def test_update_single_hotkey(self):
        """Test updating a single hotkey."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        mgr.update_hotkey("undo", "Ctrl+Shift+Z")
        
        self.assertEqual(mgr.get_hotkey("undo"), "Ctrl+Shift+Z")
    
    def test_update_multiple_hotkeys(self):
        """Test updating multiple hotkeys at once."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        new_hotkeys = {
            "undo": "Ctrl+Shift+Z",
            "redo": "Ctrl+Shift+Y",
        }
        mgr.update_hotkeys(new_hotkeys)
        
        self.assertEqual(mgr.get_hotkey("undo"), "Ctrl+Shift+Z")
        self.assertEqual(mgr.get_hotkey("redo"), "Ctrl+Shift+Y")
    
    def test_check_conflicts_no_duplicates(self):
        """Test conflict detection with no duplicates."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        conflicts = mgr.check_conflicts()
        
        # With default hotkeys, there should be no conflicts
        self.assertEqual(len(conflicts), 0)
    
    def test_check_conflicts_with_duplicates(self):
        """Test conflict detection with duplicate bindings."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        # Create a conflict
        mgr._hotkeys["test1"] = "Ctrl+A"
        mgr._hotkeys["test2"] = "Ctrl+A"
        
        conflicts = mgr.check_conflicts()
        
        self.assertIn("Ctrl+A", conflicts)
        self.assertIn("test1", conflicts["Ctrl+A"])
        self.assertIn("test2", conflicts["Ctrl+A"])
        self.assertGreaterEqual(len(conflicts["Ctrl+A"]), 2)
    
    def test_reset_to_defaults(self):
        """Test resetting all hotkeys to defaults."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        # Change some hotkeys
        mgr.update_hotkey("undo", "Ctrl+Shift+Z")
        mgr.update_hotkey("save", "Ctrl+Shift+S")
        
        # Reset
        mgr.reset_to_defaults()
        
        # Check defaults restored
        self.assertEqual(mgr.get_hotkey("undo"), "Ctrl+Z")
        self.assertEqual(mgr.get_hotkey("save"), "Ctrl+S")
    
    def test_register_callback(self):
        """Test callback registration."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        callback = MagicMock()
        mgr.register_callback("test_action", callback)
        
        self.assertIn("test_action", mgr._callbacks)
        self.assertEqual(mgr._callbacks["test_action"], callback)
    
    def test_save_hotkeys(self):
        """Test that hotkeys are saved to settings."""
        mgr = HotkeyManager(self.window, self.settings_manager)
        
        mgr.update_hotkey("undo", "Ctrl+Shift+Z")
        
        # Check settings were updated
        self.assertIn("hotkeys", self.settings_manager.settings)
        self.assertEqual(
            self.settings_manager.settings["hotkeys"]["undo"],
            "Ctrl+Shift+Z"
        )
        self.settings_manager.save.assert_called()


class TestCreateHotkeyManager(unittest.TestCase):
    """Test cases for the factory function."""
    
    def test_factory_creates_manager(self):
        """Test that factory creates a HotkeyManager."""
        window = MagicMock()
        settings_manager = MagicMock()
        settings_manager.settings = {}
        
        mgr = create_hotkey_manager(window, settings_manager)
        
        self.assertIsInstance(mgr, HotkeyManager)
    
    def test_factory_registers_callbacks(self):
        """Test that factory registers provided callbacks."""
        window = MagicMock()
        settings_manager = MagicMock()
        settings_manager.settings = {}
        
        callbacks = {
            "action1": MagicMock(),
            "action2": MagicMock(),
        }
        
        mgr = create_hotkey_manager(window, settings_manager, callbacks)
        
        self.assertIn("action1", mgr._callbacks)
        self.assertIn("action2", mgr._callbacks)


if __name__ == "__main__":
    unittest.main()
