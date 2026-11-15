# -*- coding: utf-8 -*-

from types import SimpleNamespace
import unittest

from key_events import KEY_EVENT_FIELDS, PhysicalKeyTracker


def key(name, t_down, duration=None, code=None):
    return SimpleNamespace(
        name=name,
        code=code if code is not None else name,
        tDown=t_down,
        rt=t_down,
        duration=duration,
    )


class PhysicalKeyTrackerTest(unittest.TestCase):
    def tracker(self):
        self.rows = []
        return PhysicalKeyTracker(100.0, self.rows.append)

    def test_short_press_is_one_press(self):
        tracker = self.tracker()
        downs, _ = tracker.ingest([key("space", 101.0)], [])
        _, ups = tracker.ingest([], [key("space", 101.0, 0.08)])
        self.assertEqual(len(downs), 1)
        self.assertEqual(len(ups), 1)
        self.assertEqual(downs[0]["press_id"], ups[0]["press_id"])
        self.assertAlmostEqual(downs[0]["duration_s"], 0.08)

    def test_poll_preserves_incomplete_press_until_release(self):
        class Clock:
            @staticmethod
            def getLastResetTime():
                return 100.0

        class Keyboard:
            clock = Clock()

            def __init__(self):
                self.calls = []

            def getKeys(self, **kwargs):
                self.calls.append(kwargs)
                return []

        keyboard = Keyboard()
        tracker = self.tracker()
        tracker.poll(keyboard)
        self.assertEqual(
            [
                (call["waitRelease"], call["clear"])
                for call in keyboard.calls
            ],
            [(False, False), (True, True)],
        )

    def test_two_second_hold_is_one_press(self):
        tracker = self.tracker()
        tracker.ingest([key("space", 101.0)], [])
        tracker.ingest([], [key("space", 101.0, 2.0)])
        self.assertEqual(tracker.next_press_id - 1, 1)
        self.assertAlmostEqual(tracker.events[-1]["event_session_ms"], 3000.0)

    def test_os_repeat_does_not_create_a_new_press(self):
        tracker = self.tracker()
        tracker.ingest([key("space", 101.0)], [])
        repeated_downs, _ = tracker.ingest(
            [key("space", 101.3), key("space", 101.6)],
            [],
        )
        tracker.ingest([], [key("space", 101.0, 2.0)])
        self.assertEqual(repeated_downs, [])
        self.assertEqual(tracker.next_press_id - 1, 1)
        self.assertEqual(
            [event["repeat"] for event in tracker.events],
            [0, 1, 1, 0],
        )

    def test_two_rapid_taps_are_two_presses(self):
        tracker = self.tracker()
        tracker.ingest([], [key("space", 101.0, 0.05)])
        tracker.ingest([], [key("space", 101.12, 0.05)])
        self.assertEqual(tracker.next_press_id - 1, 2)
        self.assertEqual(
            [event["press_id"] for event in tracker.events],
            [1, 1, 2, 2],
        )

    def test_keyup_after_trial_boundary_closes_the_same_press(self):
        tracker = self.tracker()
        downs, _ = tracker.ingest([key("space", 100.899)], [])
        _, ups = tracker.ingest([], [key("space", 100.899, 0.08)])
        self.assertEqual(downs[0]["press_id"], ups[0]["press_id"])
        self.assertLess(downs[0]["keydown_abs_s"], 100.9)
        self.assertGreater(ups[0]["keyup_abs_s"], 100.9)

    def test_space_held_before_block_does_not_make_a_second_press(self):
        tracker = self.tracker()
        downs, _ = tracker.ingest([key("space", 99.8)], [])
        repeats, _ = tracker.ingest([key("space", 100.1)], [])
        tracker.ingest([], [key("space", 99.8, 0.5)])
        next_downs, _ = tracker.ingest([key("space", 100.5)], [])
        self.assertEqual(len(downs), 1)
        self.assertEqual(repeats, [])
        self.assertEqual(len(next_downs), 1)
        self.assertEqual(next_downs[0]["press_id"], 2)

    def test_missing_keyup_keeps_keydown_and_missing_duration(self):
        tracker = self.tracker()
        downs, _ = tracker.ingest([key("space", 101.0)], [])
        tracker.flush()
        self.assertIsNone(downs[0]["duration_s"])
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(self.rows[0]["event_type"], "keydown")

    def test_long_escape_has_an_immediate_physical_keydown(self):
        tracker = self.tracker()
        downs, _ = tracker.ingest([key("escape", 101.0)], [])
        self.assertEqual(len(downs), 1)
        self.assertEqual(downs[0]["key"], "escape")
        self.assertIsNone(downs[0]["keyup_abs_s"])

    def test_long_low_go_gap_does_not_join_separate_taps(self):
        tracker = self.tracker()
        first, _ = tracker.ingest([], [key("space", 101.0, 0.08)])
        second, _ = tracker.ingest([], [key("space", 111.0, 0.07)])
        self.assertEqual(first[0]["press_id"], 1)
        self.assertEqual(second[0]["press_id"], 2)
        self.assertLess(first[0]["duration_s"] * 1000, 900)
        self.assertLess(second[0]["duration_s"] * 1000, 900)

    def test_forced_stop_flushes_completed_and_open_events(self):
        tracker = self.tracker()
        tracker.ingest([], [key("space", 101.0, 0.08)])
        tracker.ingest([key("space", 102.0)], [])
        tracker.flush()
        self.assertEqual(list(self.rows[0]), KEY_EVENT_FIELDS)
        self.assertEqual(
            [row["event_type"] for row in self.rows],
            ["keydown", "keyup", "keydown"],
        )
        self.assertEqual(
            [row["event_session_ms"] for row in self.rows],
            [1000.0, 1080.0, 2000.0],
        )


if __name__ == "__main__":
    unittest.main()
