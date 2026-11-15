# -*- coding: utf-8 -*-

from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import random
import unittest


PSYCHOPY_PREFS = TemporaryDirectory()
os.environ["APPDATA"] = PSYCHOPY_PREFS.name

from runtime import (
    ExperimentAbort,
    Timing,
    evaluate_trial,
    locate_key_trial,
    process_key_events,
    summarize_practice,
)
from schedule import (
    FAR,
    HEAVY_GO,
    LOW_GO,
    NEAR,
    TARGET,
    build_experiment_plan,
    load_counterbalance_schedule,
    load_set_catalog,
)
from session_utils import MAX_SESSION_SEED, normalize_session_inputs


PROJECT_DIR = Path(__file__).resolve().parent.parent
TIMING = Timing(0.45, 0.9, 0.1)
MAIN_SET_NAMES = ("set05", "set10", "set12")


def key_event(rt, onset=1.0, duration=0.08):
    return {
        "press_id": 1,
        "key": "space",
        "keydown_abs_s": onset + rt,
        "keydown_trial_s": rt,
        "keyup_abs_s": onset + rt + duration,
        "duration_s": duration,
    }


def evaluated(stimulus_type, events=(), held=False):
    runtime = {
        "key_events": list(events),
        "onset_block_s": 1.0,
        "onset_abs_s": 1.0,
        "space_held_at_onset": held,
    }
    evaluate_trial(
        {"stimulus_type": stimulus_type},
        runtime,
        1.9,
        TIMING,
    )
    return runtime


class UserBehaviorTest(unittest.TestCase):
    def test_escape_physical_keydown_aborts_immediately(self):
        class EscapeTracker:
            open_by_key = {"escape": {"key": "escape"}}

            def poll(self, _kb):
                return ([{
                    "press_id": 1,
                    "key": "escape",
                    "keydown_abs_s": 1.2,
                    "keyup_abs_s": None,
                    "duration_s": None,
                }], [])

        with self.assertRaises(ExperimentAbort):
            process_key_events(
                object(),
                [1.0],
                [{"key_events": []}],
                [],
                TIMING,
                EscapeTracker(),
            )

    def test_absolute_keydown_is_assigned_to_actual_onset(self):
        press = {
            "press_id": 1,
            "key": "space",
            "keydown_abs_s": 10.899,
            "keyup_abs_s": None,
            "duration_s": None,
        }

        class SpaceTracker:
            open_by_key = {"space": press}

            def poll(self, _kb):
                return [press], []

        rows = [{"key_events": []}, {"key_events": []}]
        process_key_events(
            object(),
            [10.0, 10.9],
            rows,
            [],
            TIMING,
            SpaceTracker(),
        )
        self.assertEqual(len(rows[0]["key_events"]), 1)
        self.assertEqual(len(rows[1]["key_events"]), 0)
        self.assertAlmostEqual(
            rows[0]["key_events"][0]["keydown_trial_s"],
            0.899,
        )

    def test_participant_fields_and_seed_are_validated_before_file_creation(self):
        normalized, seed = normalize_session_inputs(
            {
                "SubType": " ADHD-C ",
                "SubIdx": " 001 ",
                "SubSes": "02_A",
                "Seed": "1234",
            }
        )
        self.assertEqual(normalized["SubType"], "ADHD-C")
        self.assertEqual(normalized["SubIdx"], "001")
        self.assertEqual(normalized["SubSes"], "02_A")
        self.assertEqual(seed, 1234)

        _, blank_seed = normalize_session_inputs(
            {
                "SubType": "CLD",
                "SubIdx": "001",
                "SubSes": "001",
                "Seed": "",
            }
        )
        self.assertIsNone(blank_seed)

        invalid_cases = [
            {"SubType": "", "SubIdx": "001", "SubSes": "001", "Seed": ""},
            {"SubType": "CLD", "SubIdx": "../001", "SubSes": "001", "Seed": ""},
            {"SubType": "CLD", "SubIdx": "001", "SubSes": "A:1", "Seed": ""},
            {"SubType": "CLD", "SubIdx": "001", "SubSes": "001", "Seed": "-1"},
            {"SubType": "CLD", "SubIdx": "001", "SubSes": "001", "Seed": "abc"},
            {
                "SubType": "CLD",
                "SubIdx": "001",
                "SubSes": "001",
                "Seed": str(MAX_SESSION_SEED + 1),
            },
        ]
        for values in invalid_cases:
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_session_inputs(values)

    def test_go_nogo_response_matrix(self):
        cases = [
            (TARGET, [key_event(0.35)], True, ""),
            (TARGET, [], False, "go_omission"),
            (NEAR, [key_event(0.35)], False, "commission"),
            (NEAR, [], True, ""),
            (FAR, [key_event(0.35)], False, "commission"),
            (FAR, [], True, ""),
        ]
        for stimulus_type, events, expected_correct, expected_error in cases:
            with self.subTest(
                stimulus_type=stimulus_type,
                responded=bool(events),
            ):
                row = evaluated(stimulus_type, events)
                self.assertIs(row["correct"], expected_correct)
                self.assertEqual(row["error_type"], expected_error)
                self.assertTrue(row["valid_for_analysis"])

    def test_premature_boundary_and_multiple_responses(self):
        premature = evaluated(TARGET, [key_event(0.099)])
        self.assertTrue(premature["anticipatory"])
        self.assertFalse(premature["valid_for_analysis"])
        self.assertEqual(premature["correct"], "")

        threshold = evaluated(TARGET, [key_event(0.100)])
        self.assertFalse(threshold["anticipatory"])
        self.assertTrue(threshold["correct"])

        multiple = evaluated(
            TARGET,
            [key_event(0.55), key_event(0.30), key_event(0.70)],
        )
        self.assertEqual(multiple["rt_ms"], 300.0)
        self.assertEqual(multiple["response_count"], 3)
        self.assertEqual(multiple["additional_space_count"], 2)

    def test_key_held_at_onset_is_not_counted_as_a_response(self):
        target = evaluated(TARGET, [], held=True)
        self.assertTrue(target["valid_for_analysis"])
        self.assertFalse(target["responded"])
        self.assertFalse(target["correct"])
        self.assertEqual(target["error_type"], "go_omission")

        nogo = evaluated(NEAR, [], held=True)
        self.assertTrue(nogo["valid_for_analysis"])
        self.assertFalse(nogo["responded"])
        self.assertTrue(nogo["correct"])
        self.assertEqual(nogo["error_type"], "")

        new_keydown = evaluated(TARGET, [key_event(0.35)], held=True)
        self.assertTrue(new_keydown["responded"])
        self.assertTrue(new_keydown["valid_for_analysis"])
        self.assertTrue(new_keydown["correct"])

    def test_trial_location_boundaries_and_feedback_gap(self):
        rows = [{"key_events": []}, {"key_events": []}]
        onsets = [1.0, 2.2]
        self.assertIsNone(locate_key_trial(0.99, onsets, rows, 0.9))
        self.assertEqual(locate_key_trial(1.0, onsets, rows, 0.9), (0, 0.0))
        self.assertEqual(
            locate_key_trial(1.899, onsets, rows, 0.9),
            (0, 0.899),
        )
        self.assertIsNone(locate_key_trial(2.0, onsets, rows, 0.9))
        self.assertEqual(locate_key_trial(2.2, onsets, rows, 0.9), (1, 0.0))
        self.assertIsNone(locate_key_trial(3.1, onsets, rows, 0.9))

    def test_practice_cannot_be_gamed_by_press_all_or_press_none(self):
        trials = (
            [{"stimulus_type": TARGET}] * 5
            + [{"stimulus_type": NEAR}] * 5
            + [{"stimulus_type": FAR}] * 5
        )
        block = {"trials": trials}

        press_all = (
            [{"correct": True}] * 5
            + [{"correct": False}] * 10
        )
        press_none = (
            [{"correct": False}] * 5
            + [{"correct": True}] * 10
        )
        perfect = [{"correct": True}] * 15
        held_all = [{"correct": ""}] * 15

        self.assertFalse(summarize_practice(block, press_all)["practice_passed"])
        self.assertFalse(summarize_practice(block, press_none)["practice_passed"])
        self.assertTrue(summarize_practice(block, perfect)["practice_passed"])
        self.assertFalse(summarize_practice(block, held_all)["practice_passed"])


class ScheduleFuzzTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_set_catalog(PROJECT_DIR / "assets" / "sets")
        cls.cells = load_counterbalance_schedule(
            PROJECT_DIR
            / "assets"
            / "codebooks"
            / "counterbalance_schedule.tsv"
        )

    def test_all_counterbalance_cells_across_multiple_random_seeds(self):
        # Exercise every cell under enough independent shuffles to catch
        # constrained-run and practice-set allocation edge cases.
        for seed_offset in range(25):
            for cell in self.cells:
                practice, main, selection = build_experiment_plan(
                    self.catalog,
                    random.Random(20260730 + seed_offset),
                    MAIN_SET_NAMES,
                    cell,
                    None,
                )
                self.assertEqual(len(practice), 3)
                self.assertEqual(len(main), 2)
                self.assertEqual(
                    {block["block_type"] for block in main},
                    {HEAVY_GO, LOW_GO},
                )
                self.assertEqual(
                    sum(len(block["trials"]) for block in main),
                    300,
                )
                self.assertEqual(
                    selection["counterbalance_cell_id"],
                    cell["counterbalance_cell_id"],
                )
                for block in practice:
                    self.assertEqual(
                        Counter(
                            trial["stimulus_type"]
                            for trial in block["trials"]
                        ),
                        Counter({TARGET: 5, NEAR: 5, FAR: 5}),
                    )
                self.assertTrue(
                    all(
                        Path(trial["image_path"]).is_file()
                        and 1 <= trial["stimulus_pattern_id"] <= 84
                        for block in practice + main
                        for trial in block["trials"]
                    )
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
