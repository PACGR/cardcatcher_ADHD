# -*- coding: utf-8 -*-

from pathlib import Path
from tempfile import TemporaryDirectory
import ast
import csv
import os
import unittest

PSYCHOPY_PREFS = TemporaryDirectory()
os.environ["APPDATA"] = PSYCHOPY_PREFS.name

from runtime import (
    AsyncTrialWriter,
    PRACTICE_SUMMARY_FIELDS,
    RUNTIME_FIELDS,
    Timing,
    evaluate_trial,
    summarize_practice,
)
from schedule import FAR, NEAR, TARGET
from main import TIMING as MAIN_TIMING
from practice import (
    PRACTICE_RUN_COUNT,
    TIMING as PRACTICE_TIMING,
    select_standalone_practice_blocks,
)
from display_utils import (
    get_primary_display_size,
    load_cardgame_display_layout,
    measure_refresh_hz,
    serializable_display_info,
)


class RuntimeDesignTest(unittest.TestCase):
    def test_refresh_measurement_uses_real_value_or_measured_fallback(self):
        class StableWindow:
            def getActualFrameRate(self, **_kwargs):
                return 119.88

            def getMsPerFrame(self, **_kwargs):
                raise AssertionError("fallback should not be called")

        class FallbackWindow:
            def getActualFrameRate(self, **_kwargs):
                return None

            def getMsPerFrame(self, **_kwargs):
                return 6.95, 0.08, 6.944444444

        measured, source = measure_refresh_hz(StableWindow())
        self.assertEqual(measured, 119.88)
        self.assertEqual(source, "getActualFrameRate")

        measured, source = measure_refresh_hz(FallbackWindow())
        self.assertAlmostEqual(measured, 144.0, places=4)
        self.assertEqual(source, "getMsPerFrame_median")

    def test_refresh_measurement_rejects_invalid_fallback(self):
        class InvalidWindow:
            def getActualFrameRate(self, **_kwargs):
                return None

            def getMsPerFrame(self, **_kwargs):
                return 0.0, 0.0, 0.0

        with self.assertRaises(RuntimeError):
            measure_refresh_hz(InvalidWindow())

    def test_primary_display_size_is_always_a_positive_pair(self):
        width, height = get_primary_display_size((2880, 1800))
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

    def test_active_entry_points_cannot_call_retired_feedback_flow(self):
        project_dir = Path(__file__).resolve().parent.parent
        for relative_path in (
            "main.py",
            "practice.py",
            "minimal_black/main.py",
            "minimal_black/practice.py",
        ):
            with self.subTest(relative_path=relative_path):
                tree = ast.parse(
                    (project_dir / relative_path).read_text(encoding="utf-8")
                )
                calls = {
                    node.func.id
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                }
                self.assertIn("run_block", calls)
                self.assertNotIn("run_practice_block", calls)
                self.assertNotIn("show_practice_result", calls)

    def test_fixation_is_only_injected_into_minimal_black_trials(self):
        project_dir = Path(__file__).resolve().parent.parent
        expected = {
            "main.py": False,
            "practice.py": False,
            "minimal_black/main.py": True,
            "minimal_black/practice.py": True,
        }
        for relative_path, should_inject_fixation in expected.items():
            with self.subTest(relative_path=relative_path):
                tree = ast.parse(
                    (project_dir / relative_path).read_text(encoding="utf-8")
                )
                run_calls = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "run_block"
                ]
                self.assertEqual(len(run_calls), 1)
                keyword_names = {
                    keyword.arg for keyword in run_calls[0].keywords
                }
                self.assertEqual(
                    "fixation_stim" in keyword_names,
                    should_inject_fixation,
                )

    def test_cardgame_main_and_practice_share_display_layout_helper(self):
        project_dir = Path(__file__).resolve().parent.parent
        for relative_path in ("main.py", "practice.py"):
            with self.subTest(relative_path=relative_path):
                tree = ast.parse(
                    (project_dir / relative_path).read_text(encoding="utf-8")
                )
                calls = {
                    node.func.id
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                }
                self.assertIn("load_cardgame_display_layout", calls)

    def test_cardgame_cover_layout_supports_16_by_10_and_16_by_9(self):
        project_dir = Path(__file__).resolve().parent.parent
        background_path = (
            project_dir
            / "assets"
            / "backgrounds"
            / "card-catcher-background-2880x1800.png"
        )
        layout_path = (
            project_dir
            / "assets"
            / "backgrounds"
            / "card-catcher-background-2880x1800.layout.json"
        )

        native = load_cardgame_display_layout(
            (1440, 900),
            background_path,
            layout_path,
        )
        self.assertEqual(native["display_profile"], "16:10")
        self.assertEqual(native["background_size"], (1440.0, 900.0))
        self.assertEqual(native["vertical_crop_each_side_px"], 0.0)
        self.assertEqual(native["target_position"], (-444.5, 40.5))
        self.assertEqual(native["stimulus_position"], (0.0, 27.5))

        widescreen = load_cardgame_display_layout(
            (1920, 1080),
            background_path,
            layout_path,
        )
        self.assertEqual(widescreen["display_profile"], "16:9")
        self.assertEqual(widescreen["background_size"], (1920.0, 1200.0))
        self.assertEqual(widescreen["vertical_crop_each_side_px"], 60.0)
        self.assertEqual(widescreen["horizontal_crop_each_side_px"], 0.0)
        self.assertAlmostEqual(widescreen["target_position"][0], -592.6666667)
        self.assertAlmostEqual(widescreen["stimulus_position"][1], 36.6666667)

        persisted = serializable_display_info(widescreen)
        self.assertEqual(persisted["actual_screen_size"], [1920, 1080])
        self.assertEqual(persisted["background_render_size"], [1920.0, 1200.0])

        for screen_size in (
            (2880, 1800),
            (2560, 1600),
            (1920, 1200),
            (1440, 900),
            (2560, 1440),
            (1920, 1080),
            (1366, 768),
        ):
            with self.subTest(screen_size=screen_size):
                scaled = load_cardgame_display_layout(
                    screen_size,
                    background_path,
                    layout_path,
                )
                for position_key, size_key in (
                    ("target_position", "target_size"),
                    ("stimulus_position", "stimulus_size"),
                ):
                    position = scaled[position_key]
                    dimensions = scaled[size_key]
                    self.assertLessEqual(
                        abs(position[0]) + dimensions[0] / 2,
                        screen_size[0] / 2,
                    )
                    self.assertLessEqual(
                        abs(position[1]) + dimensions[1] / 2,
                        screen_size[1] / 2,
                    )

    def test_cardgame_cover_layout_rejects_unsupported_aspect_ratio(self):
        project_dir = Path(__file__).resolve().parent.parent
        with self.assertRaises(RuntimeError):
            load_cardgame_display_layout(
                (1024, 768),
                project_dir
                / "assets"
                / "backgrounds"
                / "card-catcher-background-2880x1800.png",
                project_dir
                / "assets"
                / "backgrounds"
                / "card-catcher-background-2880x1800.layout.json",
            )

    def test_standalone_practice_uses_main_task_timing(self):
        self.assertIs(PRACTICE_TIMING, MAIN_TIMING)
        self.assertEqual(PRACTICE_TIMING.stimulus_seconds, 0.45)
        self.assertEqual(PRACTICE_TIMING.trial_seconds, 0.9)

    def test_standalone_practice_uses_two_distinct_sets(self):
        blocks = [
            {"set_info": {"set_name": "set01"}},
            {"set_info": {"set_name": "set02"}},
            {"set_info": {"set_name": "set03"}},
        ]
        selected = select_standalone_practice_blocks(blocks)
        self.assertEqual(PRACTICE_RUN_COUNT, 2)
        self.assertEqual(
            [block["set_info"]["set_name"] for block in selected],
            ["set01", "set02"],
        )

    def test_standalone_practice_rejects_duplicate_sets(self):
        blocks = [
            {"set_info": {"set_name": "set01"}},
            {"set_info": {"set_name": "set01"}},
        ]
        with self.assertRaises(RuntimeError):
            select_standalone_practice_blocks(blocks)

    def test_runtime_output_matches_approved_log_schema(self):
        self.assertEqual(len(RUNTIME_FIELDS), 37)
        self.assertEqual(
            RUNTIME_FIELDS[5:10],
            [
                "counterbalance_cell_id",
                "onset_session_ms",
                "overall_trial_number",
                "block_index",
                "block_type",
            ],
        )
        self.assertIn("nogo_count_since_last_target", RUNTIME_FIELDS)
        self.assertIn("press_duration", RUNTIME_FIELDS)
        self.assertNotIn("space_held_too_long", RUNTIME_FIELDS)
        self.assertIn("valid_for_analysis", RUNTIME_FIELDS)
        self.assertIn("too_early_response", RUNTIME_FIELDS)

    def test_practice_requires_each_subcriterion(self):
        trials = (
            [{"stimulus_type": TARGET}] * 5
            + [{"stimulus_type": NEAR}] * 5
            + [{"stimulus_type": FAR}] * 5
        )
        passing_runtime = (
            [{"correct": True}] * 4
            + [{"correct": False}]
            + [{"correct": True}] * 8
            + [{"correct": False}] * 2
        )
        summary = summarize_practice({"trials": trials}, passing_runtime)
        self.assertEqual(summary["overall_correct"], 12)
        self.assertTrue(summary["practice_passed"])

        target_failure = (
            [{"correct": True}] * 3
            + [{"correct": False}] * 2
            + [{"correct": True}] * 9
            + [{"correct": False}]
        )
        summary = summarize_practice({"trials": trials}, target_failure)
        self.assertEqual(summary["overall_correct"], 12)
        self.assertFalse(summary["target_passed"])
        self.assertFalse(summary["practice_passed"])

    def test_boolean_writer_preserves_nullable_blank(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "boolean.tsv"
            writer = AsyncTrialWriter(
                path,
                ["true_value", "false_value", "missing_value"],
            )
            writer.submit(
                {
                    "true_value": True,
                    "false_value": False,
                    "missing_value": "",
                }
            )
            writer.close()
            with path.open("r", encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(row["true_value"], "1")
            self.assertEqual(row["false_value"], "0")
            self.assertEqual(row["missing_value"], "")

    def test_practice_evaluation_keeps_events_mutable_until_saved(self):
        trial = {"stimulus_type": TARGET}
        runtime = {
            "key_events": [
                {
                    "press_id": 1,
                    "key": "space",
                    "keydown_abs_s": 1.4,
                    "keydown_trial_s": 0.4,
                    "keyup_abs_s": None,
                    "duration_s": None,
                }
            ],
            "onset_block_s": 0.0,
            "onset_abs_s": 1.0,
        }
        timing = Timing(2.0, 2.0, 0.1)
        evaluate_trial(
            trial,
            runtime,
            2.0,
            timing,
        )
        self.assertIsInstance(runtime["key_events"], list)
        self.assertEqual(runtime["keyup_ms"], "")
        runtime["key_events"][0].update(
            {
                "keyup_abs_s": 1.5,
                "duration_s": 0.1,
            }
        )
        evaluate_trial(trial, runtime, 2.0, timing)
        self.assertIsInstance(runtime["key_events"], list)
        self.assertEqual(runtime["correct"], True)
        self.assertEqual(runtime["keyup_ms"], 500.0)
        self.assertEqual(runtime["press_duration_ms"], 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
