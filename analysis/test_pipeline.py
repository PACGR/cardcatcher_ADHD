# -*- coding: utf-8 -*-

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import json
import os
import random
import subprocess
import sys
import unittest

from analysis.run_pipeline import normalize_trial_schema
from schedule import (
    FAR,
    HEAVY_GO,
    NEAR,
    TARGET,
    build_experiment_plan,
    load_counterbalance_schedule,
    load_set_catalog,
    write_planned_schedule,
)


PROJECT_DIR = Path(__file__).resolve().parent.parent
PIPELINE = Path(__file__).resolve().parent / "run_pipeline.py"
MAIN_SET_NAMES = ("set05", "set10", "set12")

RUNTIME_FIELDS = [
    "subject", "session", "subject_type", "date", "session_seed",
    "counterbalance_cell_id", "onset_session_ms", "overall_trial_number",
    "block_index", "block_type", "within_block_trial_number", "target_set",
    "target_pattern_id", "stimulus_pattern_id", "stimulus_type",
    "position_in_dominant_run", "nogo_count_since_last_target",
    "response_required", "responded", "response_key", "response_count",
    "additional_space_count", "correct", "press_duration", "rt_ms",
    "error_type", "valid_for_analysis", "too_early_response",
    "exclusion_reasons", "scheduled_stimulus_duration_ms",
    "actual_stimulus_duration_ms", "response_window_ms",
    "actual_trial_duration_ms", "refresh_hz",
    "stimulus_frames", "trial_frames", "image_path",
]


def digest(path):
    value = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def read_tsv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_tsv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def make_trial_row(
    subject_info,
    seed,
    trial,
    *,
    responded,
    rt_ms,
    press_duration,
    correct,
    error_type,
    valid_for_analysis,
    too_early_response,
    exclusion_reasons,
    stimulus_ms,
    trial_ms,
    stimulus_frames,
    trial_frames,
):
    return {
        "subject": subject_info["SubIdx"],
        "session": subject_info["SubSes"],
        "subject_type": subject_info["SubType"],
        "date": subject_info["date"],
        "session_seed": seed,
        "counterbalance_cell_id": trial.get("counterbalance_cell_id", ""),
        "onset_session_ms": round(trial["global_trial_index"] * trial_ms, 3),
        "overall_trial_number": trial["global_trial_index"],
        "block_index": trial["block_index"],
        "block_type": trial["block_type"],
        "within_block_trial_number": trial["block_trial_index"],
        "target_set": trial["target_set"],
        "target_pattern_id": trial["target_pattern_id"],
        "stimulus_pattern_id": trial["stimulus_pattern_id"],
        "stimulus_type": trial["stimulus_type"],
        "position_in_dominant_run": trial.get("position_in_dominant_run", ""),
        "nogo_count_since_last_target": trial.get("nogo_count_since_last_target", ""),
        "response_required": 1 if trial["stimulus_type"] == TARGET else 0,
        "responded": 1 if responded else 0,
        "response_key": "space" if responded else "",
        "response_count": 1 if responded else 0,
        "additional_space_count": 0,
        "correct": "" if correct == "" else (1 if correct else 0),
        "press_duration": press_duration,
        "rt_ms": rt_ms,
        "error_type": error_type,
        "valid_for_analysis": 1 if valid_for_analysis else 0,
        "too_early_response": 1 if too_early_response else 0,
        "exclusion_reasons": exclusion_reasons,
        "scheduled_stimulus_duration_ms": stimulus_ms,
        "actual_stimulus_duration_ms": stimulus_ms,
        "response_window_ms": trial_ms,
        "actual_trial_duration_ms": trial_ms,
        "refresh_hz": 60.0,
        "stimulus_frames": stimulus_frames,
        "trial_frames": trial_frames,
        "image_path": str(Path(trial["image_path"]).relative_to(PROJECT_DIR)),
    }


def write_synthetic_session(
    raw_dir,
    catalog,
    cell,
    *,
    sub_type,
    sub_idx,
    sub_ses,
    date_str,
    seed,
    stimulus_s,
    trial_s,
    premature_s,
    max_trials=None,
    inject_reference_errors=False,
    include_practice_files=False,
):
    raw_dir.mkdir(parents=True, exist_ok=True)
    session_id = f"{sub_type}-{sub_idx}_{sub_ses}_{date_str}"
    subject_info = {
        "SubType": sub_type,
        "SubIdx": sub_idx,
        "SubSes": sub_ses,
        "date": date_str,
    }
    practice_blocks, main_blocks, selection = build_experiment_plan(
        catalog,
        random.Random(seed),
        MAIN_SET_NAMES,
        cell,
        None,
    )

    config_path = raw_dir / f"{session_id}_config.json"
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "subject": subject_info,
                "session_seed": seed,
                "target_selection_mode": "fixed_rank1_triplet_counterbalanced",
                "main_set_names": list(MAIN_SET_NAMES),
                "selection": selection,
                "timing": {
                    "stimulus_seconds": stimulus_s,
                    "trial_seconds": trial_s,
                    "premature_seconds": premature_s,
                },
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    schedule_path = raw_dir / f"{session_id}_schedule.tsv"
    write_planned_schedule(schedule_path, main_blocks, PROJECT_DIR)

    stimulus_ms = stimulus_s * 1000.0
    trial_ms = trial_s * 1000.0
    stimulus_frames = int(round(stimulus_s * 60))
    trial_frames = int(round(trial_s * 60))

    if include_practice_files:
        practice_prefix = f"{session_id}_p01-p02_practice"
        write_planned_schedule(
            raw_dir / f"{practice_prefix}_schedule.tsv",
            practice_blocks[:2],
            PROJECT_DIR,
        )
        practice_rows = [
            make_trial_row(
                subject_info,
                seed,
                trial,
                responded=(trial["stimulus_type"] == TARGET),
                rt_ms=350.0 if trial["stimulus_type"] == TARGET else "",
                press_duration=85.0 if trial["stimulus_type"] == TARGET else "",
                correct=True,
                error_type="",
                valid_for_analysis=True,
                too_early_response=False,
                exclusion_reasons="",
                stimulus_ms=stimulus_ms,
                trial_ms=trial_ms,
                stimulus_frames=stimulus_frames,
                trial_frames=trial_frames,
            )
            for block in practice_blocks[:2]
            for trial in block["trials"]
        ]
        write_tsv(raw_dir / f"{practice_prefix}_trials.tsv", practice_rows, RUNTIME_FIELDS)

    trial_rows = []
    for block in main_blocks:
        counts = {TARGET: 0, NEAR: 0, FAR: 0}
        is_heavy = block["block_type"] == HEAVY_GO
        for trial in block["trials"]:
            if max_trials is not None and len(trial_rows) >= max_trials:
                break
            stim_type = trial["stimulus_type"]
            counts[stim_type] += 1
            ordinal = counts[stim_type]

            if inject_reference_errors and is_heavy:
                if stim_type == TARGET and ordinal == 1:
                    row_kwargs = dict(
                        responded=True,
                        rt_ms=80.0,
                        press_duration=85.0,
                        correct="",
                        error_type="anticipatory_excluded",
                        valid_for_analysis=False,
                        too_early_response=True,
                        exclusion_reasons="anticipatory_lt_100ms",
                    )
                elif stim_type == TARGET and ordinal == 2:
                    row_kwargs = dict(
                        responded=True,
                        rt_ms=320.0,
                        press_duration="",
                        correct=True,
                        error_type="",
                        valid_for_analysis=True,
                        too_early_response=False,
                        exclusion_reasons="",
                    )
                elif stim_type == TARGET:
                    row_kwargs = dict(
                        responded=True,
                        rt_ms=320.0,
                        press_duration=85.0,
                        correct=True,
                        error_type="",
                        valid_for_analysis=True,
                        too_early_response=False,
                        exclusion_reasons="",
                    )
                elif stim_type == NEAR and ordinal <= 9:
                    row_kwargs = dict(
                        responded=True,
                        rt_ms=340.0,
                        press_duration=85.0,
                        correct=False,
                        error_type="commission",
                        valid_for_analysis=True,
                        too_early_response=False,
                        exclusion_reasons="",
                    )
                elif stim_type == FAR and ordinal <= 5:
                    row_kwargs = dict(
                        responded=True,
                        rt_ms=340.0,
                        press_duration=85.0,
                        correct=False,
                        error_type="commission",
                        valid_for_analysis=True,
                        too_early_response=False,
                        exclusion_reasons="",
                    )
                else:
                    row_kwargs = dict(
                        responded=False,
                        rt_ms="",
                        press_duration="",
                        correct=True,
                        error_type="",
                        valid_for_analysis=True,
                        too_early_response=False,
                        exclusion_reasons="",
                    )
            else:
                is_target = stim_type == TARGET
                row_kwargs = dict(
                    responded=is_target,
                    rt_ms=360.0 if is_target else "",
                    press_duration=85.0 if is_target else "",
                    correct=True,
                    error_type="",
                    valid_for_analysis=True,
                    too_early_response=False,
                    exclusion_reasons="",
                )

            trial_rows.append(
                make_trial_row(
                    subject_info,
                    seed,
                    trial,
                    stimulus_ms=stimulus_ms,
                    trial_ms=trial_ms,
                    stimulus_frames=stimulus_frames,
                    trial_frames=trial_frames,
                    **row_kwargs,
                )
            )

    write_tsv(raw_dir / f"{session_id}_trials.tsv", trial_rows, RUNTIME_FIELDS)


class PipelineSchemaCompatibilityTest(unittest.TestCase):
    def test_current_trial_schema_is_exposed_to_legacy_analysis_names(self):
        current = {
            "overall_trial_number": "12",
            "within_block_trial_number": "7",
            "valid_for_analysis": "1",
            "too_early_response": "0",
            "press_duration": "83.5",
        }
        planned = {
            "global_trial_index": "12",
            "phase": "Block A",
            "stimulus_pattern": "001010100",
        }
        normalized = normalize_trial_schema(current, planned)
        self.assertEqual(normalized["global_trial_index"], "12")
        self.assertEqual(normalized["block_trial_index"], "7")
        self.assertEqual(normalized["valid_for_primary"], "1")
        self.assertEqual(normalized["anticipatory"], "0")
        self.assertEqual(normalized["press_duration_ms"], "83.5")
        self.assertEqual(normalized["phase"], "Block A")
        self.assertEqual(normalized["stimulus_pattern"], "001010100")


class PipelineIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.data_dir = Path(cls.temporary.name) / "data"
        cls.output_dir = Path(cls.temporary.name) / "output"
        catalog = load_set_catalog(PROJECT_DIR / "assets" / "sets")
        cells = load_counterbalance_schedule(
            PROJECT_DIR / "assets" / "codebooks" / "counterbalance_schedule.tsv"
        )

        write_synthetic_session(
            cls.data_dir / "CLD-002_ses-01" / "raw",
            catalog,
            cells[0],
            sub_type="CLD",
            sub_idx="002",
            sub_ses="001",
            date_str="2026-08-01_10h00.00.000",
            seed=20260801,
            stimulus_s=0.45,
            trial_s=0.9,
            premature_s=0.1,
            inject_reference_errors=True,
            include_practice_files=True,
        )
        write_synthetic_session(
            cls.data_dir / "CLD-003_ses-01" / "raw",
            catalog,
            cells[1],
            sub_type="CLD",
            sub_idx="003",
            sub_ses="001",
            date_str="2026-08-01_11h00.00.000",
            seed=20260802,
            stimulus_s=0.40,
            trial_s=0.8,
            premature_s=0.1,
            max_trials=120,
        )

        cls.all_raw_paths = sorted(cls.data_dir.rglob("*_trials.tsv"))
        cls.raw_paths = [
            path
            for path in cls.all_raw_paths
            if not path.name.endswith("_practice_trials.tsv")
        ]
        cls.raw_hashes_before = {
            path: digest(path) for path in cls.all_raw_paths
        }

        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(PIPELINE),
                "--data-dir",
                str(cls.data_dir),
                "--output-dir",
                str(cls.output_dir),
            ],
            cwd=PROJECT_DIR,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + "\n" + result.stderr)
        cls.stdout = result.stdout
        cls.processed, cls.processed_fields = read_tsv(
            cls.output_dir / "processed_trials.tsv"
        )
        cls.summary, cls.summary_fields = read_tsv(
            cls.output_dir / "participant_summary.tsv"
        )
        cls.contrasts, _ = read_tsv(cls.output_dir / "participant_contrasts.tsv")
        cls.qc, cls.qc_fields = read_tsv(cls.output_dir / "session_qc.tsv")
        with (cls.output_dir / "analysis_manifest.json").open(
            "r", encoding="utf-8"
        ) as handle:
            cls.manifest = json.load(handle)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_raw_files_are_unchanged(self):
        after = {path: digest(path) for path in self.all_raw_paths}
        self.assertEqual(self.raw_hashes_before, after)

    def test_every_trial_is_present_once(self):
        expected = 0
        for path in self.raw_paths:
            rows, _ = read_tsv(path)
            expected += len(rows)
        self.assertEqual(len(self.processed), expected)
        keys = [
            (row["source_session_id"], row["global_trial_index"])
            for row in self.processed
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_schema_and_joins(self):
        self.assertEqual(len(self.processed_fields), len(set(self.processed_fields)))
        self.assertTrue(all(row["stimulus_manifest_joined"] == "True" for row in self.processed))
        self.assertTrue(all(row["manifest_missing_count"] == "0" for row in self.qc))
        complete = [row for row in self.qc if row["session_complete"] == "True"]
        incomplete = [row for row in self.qc if row["session_complete"] == "False"]
        self.assertTrue(all(row["schedule_mismatch_count"] == "0" for row in complete))
        self.assertTrue(all(row["primary_ready"] == "True" for row in complete))
        self.assertTrue(
            all(int(row["schedule_mismatch_count"]) > 0 for row in incomplete)
        )

    def test_practice_and_quartile_flags(self):
        self.assertTrue(
            all(
                row["primary_include"] == "False"
                for row in self.processed
                if row["phase"] == "Practice"
            )
        )
        boundary = next(
            row
            for row in self.processed
            if row["source_session_id"].startswith("CLD-002_")
            and row["phase"] == "Block A"
            and row["block_trial_index"] == "38"
        )
        self.assertEqual(boundary["trial_quartile"], "1")

    def test_cld002_reference_metrics(self):
        heavy = next(
            row
            for row in self.summary
            if row["source_session_id"].startswith("CLD-002_")
            and row["block_type"] == "Heavy-go"
        )
        self.assertAlmostEqual(float(heavy["target_hit_rate"]), 1.0, places=6)
        self.assertAlmostEqual(
            float(heavy["near_commission_rate"]), 9 / 19, places=6
        )
        self.assertAlmostEqual(
            float(heavy["far_commission_rate"]), 5 / 19, places=6
        )
        self.assertAlmostEqual(float(heavy["dprime_loglinear"]), 2.94188, places=5)

    def test_protocol_and_keyup_warnings(self):
        self.assertGreaterEqual(len(self.manifest["protocol_counts"]), 2)
        self.assertTrue(
            any("Multiple timing protocols" in item for item in self.manifest["warnings"])
        )
        complete = [row for row in self.qc if row["session_complete"] == "True"]
        self.assertTrue(all(row["press_duration_ready"] == "False" for row in complete))
        self.assertTrue(
            all(int(row["keyup_quality_flag_count"]) > 0 for row in complete)
        )

    def test_expected_output_shapes(self):
        expected_summary_rows = len(
            {
                (row["source_session_id"], row["block_index"])
                for row in self.processed
            }
        )
        complete_sessions = sum(
            row["session_complete"] == "True" for row in self.qc
        )
        self.assertEqual(len(self.summary), expected_summary_rows)
        self.assertEqual(len(self.contrasts), complete_sessions)
        self.assertEqual(self.manifest["processed_trial_count"], len(self.processed))


if __name__ == "__main__":
    unittest.main(verbosity=2)
