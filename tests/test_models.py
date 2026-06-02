"""Unit tests for MacroForge data models."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Action, ActionListModel, HistoryManager, ProfileManager


class TestAction(unittest.TestCase):
    def test_default_type_is_key(self):
        a = Action(key="w", duration=0.5)
        self.assertEqual(a.action_type, "key")
        self.assertFalse(a.is_image())
        self.assertFalse(a.is_click())
        self.assertFalse(a.is_pause())

    def test_serialization_roundtrip(self):
        a = Action(
            key="w", duration=1.0, hold_mode=True, lane=1,
            action_type="key", label="forward"
        )
        d = a.to_dict()
        b = Action.from_dict(d)
        self.assertEqual(b.key, "w")
        self.assertEqual(b.duration, 1.0)
        self.assertTrue(b.hold_mode)
        self.assertEqual(b.lane, 1)
        self.assertEqual(b.label, "forward")

    def test_from_dict_missing_fields_uses_defaults(self):
        d = {"key": "space", "duration": 0.3}
        a = Action.from_dict(d)
        self.assertEqual(a.action_type, "key")


class TestHistoryManager(unittest.TestCase):
    def test_undo_redo(self):
        h = HistoryManager()
        actions = [Action("a", 0.5)]
        h.push(actions)             # save state "a"
        actions[0].key = "b"      # mutate to "b"
        # undo restores the saved "a" state
        result = h.undo(actions)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].key, "a")
        # redo restores the "b" state that was passed in
        result2 = h.redo(result)
        self.assertIsNotNone(result2)
        self.assertEqual(result2[0].key, "b")

    def test_max_size(self):
        h = HistoryManager()
        h.max_size = 3
        for i in range(5):
            h.push([Action(str(i), 0.1)])
        self.assertEqual(len(h.undo_stack), 3)


class TestActionListModel(unittest.TestCase):
    def test_insert_action_uses_requested_position(self):
        model = ActionListModel([Action("a", 0.1), Action("c", 0.1)])
        row = model.insert_action(1, Action("b", 0.1))
        self.assertEqual(row, 1)
        self.assertEqual([action.key for action in model.actions()], ["a", "b", "c"])

    def test_move_action_reorders_backing_list(self):
        model = ActionListModel([Action("a", 0.1), Action("b", 0.1), Action("c", 0.1)])
        self.assertTrue(model.move_action(0, 2))
        self.assertEqual([action.key for action in model.actions()], ["b", "c", "a"])


class TestProfileManager(unittest.TestCase):
    def test_save_load_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProfileManager()
            pm.base_dir = tmpdir
            pm.profiles_dir = os.path.join(tmpdir, "profiles")
            pm.settings_file = os.path.join(tmpdir, "settings.json")
            os.makedirs(pm.profiles_dir, exist_ok=True)

            actions = [Action("w", 0.5), Action("a", 0.5)]
            settings = {"loops": 5}
            pm.save_profile(actions, settings, "test")

            data = pm.load_profile("test")
            self.assertIsNotNone(data)
            self.assertEqual(data["profile"], "test")
            self.assertEqual(len(data["actions"]), 2)
            self.assertEqual(data["settings"]["loops"], 5)

    def test_list_profiles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProfileManager()
            pm.base_dir = tmpdir
            pm.profiles_dir = os.path.join(tmpdir, "profiles")
            pm.settings_file = os.path.join(tmpdir, "settings.json")
            os.makedirs(pm.profiles_dir, exist_ok=True)
            pm.new_profile("alpha")
            pm.new_profile("beta")
            names = pm.list_profiles()
            self.assertIn("alpha", names)
            self.assertIn("beta", names)

    def test_reordered_rows_persist_after_profile_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProfileManager()
            pm.base_dir = tmpdir
            pm.profiles_dir = os.path.join(tmpdir, "profiles")
            pm.settings_file = os.path.join(tmpdir, "settings.json")
            os.makedirs(pm.profiles_dir, exist_ok=True)
            model = ActionListModel([Action("a", 0.1), Action("b", 0.1), Action("c", 0.1)])
            model.move_action(0, 2)

            pm.save_profile(model.actions(), {}, "sorted")
            data = pm.load_profile("sorted")
            reloaded = [Action.from_dict(raw) for raw in data["actions"]]
            self.assertEqual([action.key for action in reloaded], ["b", "c", "a"])


if __name__ == "__main__":
    unittest.main()
