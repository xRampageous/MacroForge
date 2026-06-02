"""Regression tests for execution engine sequence looping."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import ExecutionEngine
from models import Action


class DummyInput:
    def key_down(self, _key):
        pass

    def key_up(self, _key):
        pass


class TestExecutionEngineLoops(unittest.TestCase):
    def test_loop_until_found_finishes_every_timeline_row_before_restarting(self):
        played = []
        statuses = []
        image_searches = 0

        with patch("engine.PlatformInput", return_value=DummyInput()):
            runner = ExecutionEngine(
                statuses.append,
                lambda idx, _duration: played.append(idx),
                lambda: None,
                lambda _progress: None,
            )

        actions = [Action(f"key-{idx}", 0.0) for idx in range(12)]
        actions[7] = Action(
            "[IMAGE]",
            0.0,
            action_type="image",
            image_data="template",
            loop_until_found=True,
        )
        runner.actions = actions
        runner.simulation_mode = True
        runner.human_curve = False

        def fake_image_search(_action):
            nonlocal image_searches
            image_searches += 1
            runner._last_image_found = image_searches >= 2

        runner._exec_image_search = fake_image_search
        runner.run(1)

        self.assertEqual(played, list(range(12)) * 2)
        self.assertEqual(runner.loops_completed_count, 1)
        self.assertIn("Image not found — looping sequence after remaining actions...", statuses)


if __name__ == "__main__":
    unittest.main()
