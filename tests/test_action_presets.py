"""Tests for the action presets system."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import MagicMock, patch
import tempfile
import shutil

from action_presets import ActionPreset, ActionPresetManager, get_preset_manager


class TestActionPreset(unittest.TestCase):
    """Test cases for ActionPreset dataclass."""
    
    def test_preset_creation(self):
        """Test creating a preset."""
        preset = ActionPreset(
            name="Test Preset",
            description="Test description",
            action_type="key",
            key="enter",
            duration=0.5
        )
        
        self.assertEqual(preset.name, "Test Preset")
        self.assertEqual(preset.action_type, "key")
        self.assertEqual(preset.key, "enter")
        self.assertEqual(preset.duration, 0.5)
    
    def test_preset_to_dict(self):
        """Test converting preset to dictionary."""
        preset = ActionPreset(
            name="Test",
            description="Desc",
            action_type="image",
            similarity=0.9
        )
        
        data = preset.to_dict()
        
        self.assertEqual(data['name'], "Test")
        self.assertEqual(data['action_type'], "image")
        self.assertEqual(data['similarity'], 0.9)
    
    def test_preset_from_dict(self):
        """Test creating preset from dictionary."""
        data = {
            'name': 'From Dict',
            'description': 'Test',
            'action_type': 'click',
            'click_button': 'right',
            'tags': ['test', 'click']
        }
        
        preset = ActionPreset.from_dict(data)
        
        self.assertEqual(preset.name, "From Dict")
        self.assertEqual(preset.action_type, "click")
        self.assertEqual(preset.click_button, "right")
    
    def test_preset_apply_to_action(self):
        """Test applying preset to an action."""
        preset = ActionPreset(
            name="Image Search",
            description="Test",
            action_type="image",
            similarity=0.95,
            wait_timeout=5.0
        )
        
        action = MagicMock()
        action.action_type = "key"
        action.similarity = 0.8
        action.wait_timeout = 0.0
        
        preset.apply_to_action(action)
        
        self.assertEqual(action.action_type, "image")
        self.assertEqual(action.similarity, 0.95)
        self.assertEqual(action.wait_timeout, 5.0)


class TestActionPresetManager(unittest.TestCase):
    """Test cases for ActionPresetManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ActionPresetManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_defaults_loaded(self):
        """Test that default presets are loaded."""
        self.assertGreater(len(self.manager.get_all_presets()), 0)
    
    def test_get_preset(self):
        """Test getting a preset by name."""
        preset = self.manager.get_preset("Quick Key Press")
        
        self.assertIsNotNone(preset)
        self.assertEqual(preset.name, "Quick Key Press")
        self.assertEqual(preset.action_type, "key")
    
    def test_get_preset_not_found(self):
        """Test getting non-existent preset."""
        preset = self.manager.get_preset("Non Existent")
        
        self.assertIsNone(preset)
    
    def test_add_preset(self):
        """Test adding a custom preset."""
        preset = ActionPreset(
            name="Custom Test",
            description="Test preset",
            action_type="pause",
            duration=2.0
        )
        
        result = self.manager.add_preset(preset)
        
        self.assertTrue(result)
        
        # Verify it was added
        retrieved = self.manager.get_preset("Custom Test")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.duration, 2.0)
    
    def test_delete_preset(self):
        """Test deleting a preset."""
        # First add a preset
        preset = ActionPreset(name="To Delete", description="Test", action_type="key")
        self.manager.add_preset(preset)
        
        # Delete it
        result = self.manager.delete_preset("To Delete")
        
        self.assertTrue(result)
        self.assertIsNone(self.manager.get_preset("To Delete"))
    
    def test_delete_preset_not_found(self):
        """Test deleting non-existent preset."""
        result = self.manager.delete_preset("Non Existent")
        
        self.assertFalse(result)
    
    def test_duplicate_preset(self):
        """Test duplicating a preset."""
        original = self.manager.get_preset("Quick Key Press")
        
        duplicate = self.manager.duplicate_preset("Quick Key Press", "Quick Key Copy")
        
        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.name, "Quick Key Copy")
        self.assertEqual(duplicate.action_type, original.action_type)
        self.assertEqual(duplicate.duration, original.duration)
    
    def test_get_by_category(self):
        """Test getting presets by category."""
        key_presets = self.manager.get_presets_by_category("Key Actions")
        
        self.assertGreater(len(key_presets), 0)
        for preset in key_presets:
            self.assertEqual(preset.category, "Key Actions")
    
    def test_get_by_type(self):
        """Test getting presets by action type."""
        image_presets = self.manager.get_presets_by_type("image")
        
        self.assertGreater(len(image_presets), 0)
        for preset in image_presets:
            self.assertEqual(preset.action_type, "image")
    
    def test_get_categories(self):
        """Test getting all categories."""
        categories = self.manager.get_categories()
        
        self.assertIn("Key Actions", categories)
        self.assertIn("Image Actions", categories)
    
    def test_search_presets(self):
        """Test searching presets."""
        results = self.manager.search_presets("key")
        
        self.assertGreater(len(results), 0)
        # All results should contain "key" in name or description
        for preset in results:
            self.assertTrue(
                "key" in preset.name.lower() or
                "key" in preset.description.lower()
            )
    
    def test_create_from_action(self):
        """Test creating preset from action."""
        action = MagicMock()
        action.action_type = "image"
        action.similarity = 0.92
        action.wait_timeout = 3.0
        action.key = ""
        
        preset = self.manager.create_from_action(
            "From Action",
            "Created from action",
            action,
            category="Custom"
        )
        
        self.assertEqual(preset.name, "From Action")
        self.assertEqual(preset.action_type, "image")
        self.assertEqual(preset.similarity, 0.92)
        self.assertEqual(preset.wait_timeout, 3.0)


class TestGlobalPresetManager(unittest.TestCase):
    """Test cases for global preset manager function."""
    
    def test_get_preset_manager_singleton(self):
        """Test that get_preset_manager returns singleton."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the default location to use temp dir
            with patch('action_presets._preset_manager', None):
                with patch.object(ActionPresetManager, '__init__', lambda self, base_dir=None: None):
                    # Force new instance
                    import action_presets
                    action_presets._preset_manager = None
                    
                    mgr1 = get_preset_manager()
                    mgr2 = get_preset_manager()
                    
                    self.assertIs(mgr1, mgr2)


if __name__ == "__main__":
    unittest.main()
