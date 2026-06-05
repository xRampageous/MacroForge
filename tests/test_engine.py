"""Regression tests for execution engine sequence looping."""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import ExecutionEngine, ImageSearchTiming
from models import Action


class DummyInput:
    def key_down(self, _key):
        pass

    def key_up(self, _key):
        pass


class TestExecutionEngineLoops(unittest.TestCase):
    def test_image_search_timing_extends_deadline_for_pause(self):
        now = [100.0]
        timing = ImageSearchTiming(5.0, now=lambda: now[0])

        now[0] = 102.0
        self.assertAlmostEqual(timing.remaining(), 3.0)
        timing.extend_for_pause(4.0)
        self.assertAlmostEqual(timing.remaining(), 7.0)

        now[0] = 109.1
        self.assertTrue(timing.expired())

    def test_image_without_template_reports_waiting_then_missed(self):
        states = []
        with patch("engine.PlatformInput", return_value=DummyInput()):
            runner = ExecutionEngine(lambda _message: None, lambda *_args: None, lambda: None, lambda _progress: None)
        runner.current_action_index = 4
        runner.image_state_cb = lambda idx, state: states.append((idx, state))

        runner._exec_image_search(Action("[IMAGE]", 0.0, action_type="image"))

        self.assertEqual(states, [(4, "Waiting"), (4, "Missed")])

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

    def test_image_wait_timeout_is_reported_as_visible_duration(self):
        played = []
        with patch("engine.PlatformInput", return_value=DummyInput()):
            runner = ExecutionEngine(
                lambda _message: None,
                lambda idx, duration: played.append((idx, duration)),
                lambda: None,
                lambda _progress: None,
            )
        runner.actions = [Action("[IMAGE]", 0.05, action_type="image", wait_timeout=6.5)]
        runner._exec_image_search = lambda _action: None
        runner.run(1)
        self.assertEqual(played, [(0, 6.5)])

    def test_invalid_top_level_loop_count_runs_once(self):
        played = []
        statuses = []
        with patch("engine.PlatformInput", return_value=DummyInput()):
            runner = ExecutionEngine(
                statuses.append,
                lambda idx, _duration: played.append(idx),
                lambda: None,
                lambda _progress: None,
            )
        runner.actions = [Action("enter", 0.0)]
        runner.simulation_mode = True
        runner.human_curve = False

        runner.run(0)

        self.assertEqual(played, [0])
        self.assertEqual(runner.loops_completed_count, 1)
        self.assertIn("Loop 1/1", statuses)


if __name__ == "__main__":
    unittest.main()
