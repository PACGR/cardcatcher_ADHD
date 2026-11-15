# -*- coding: utf-8 -*-
"""Create analysis-ready trial, participant, stimulus, sequence, and QC tables.

The pipeline is intentionally dependency-free. It never modifies raw files and
records input hashes and processing settings for reproducibility.
"""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from statistics import NormalDist, mean, median, stdev
import csv
import json
import math


PIPELINE_VERSION = "1.1.0"
PROJECT_DIR = Path(__file__).resolve().parent.parent

SCHEDULE_COMPARE_FIELDS = [
    "global_trial_index",
    "block_index",
    "phase",
    "block_type",
    "counterbalance_cell_id",
    "block_trial_index",
    "target_set",
    "target_pattern_id",
    "stimulus_pattern_id",
    "target_pattern",
    "stimulus_pattern",
    "stimulus_type",
    "is_minority",
    "dominant_run_index",
    "dominant_run_length",
    "position_in_dominant_run",
    "image_path",
]

STIMULUS_METRIC_FIELDS = [
    "active_indices",
    "canonical_d4",
    "fixed_overlap",
    "fixed_hamming",
    "d4_min_distance",
    "low_level_distance",
    "structural_distance",
    "similarity_score",
    "selection_priority",
    "center_included",
    "orthogonal_pairs",
    "diagonal_pairs",
    "components_4",
    "components_8",
    "symmetry_count",
    "orbit_size",
]

DERIVED_TRIAL_FIELDS = [
    "source_session_id",
    "source_trials_file",
    "protocol_id",
    "config_stimulus_ms",
    "config_trial_ms",
    "config_premature_ms",
    "candidate_pool_size",
    "candidate_pool_maximum",
    "stimulus_manifest_joined",
    "stimulus_rank",
    *[f"stimulus_{field}" for field in STIMULUS_METRIC_FIELDS],
    "is_main",
    "is_go",
    "is_nogo",
    "hit",
    "omission",
    "commission",
    "correct_rejection",
    "frame_ms",
    "stimulus_timing_error_ms",
    "trial_timing_error_ms",
    "timing_warning",
    "timing_bad_gt_frame",
    "timing_flag_reasons",
    "keyup_quality_flag",
    "keyup_quality_reasons",
    "primary_include",
    "rt_eligible",
    "prev_stimulus_type",
    "prev_responded",
    "prev_correct",
    "prev_error_type",
    "prev_rt_ms",
    "post_error",
    "post_nogo",
    "stimulus_switch",
    "trial_quartile",
    "time_on_task_fraction",
    "rt_group_median_ms",
    "rt_group_mad_ms",
    "rt_outlier_mad",
    "rt_include_strict",
]

SUMMARY_FIELDS = [
    "source_session_id",
    "protocol_id",
    "subject_type",
    "subject",
    "session",
    "date",
    "session_seed",
    "block_index",
    "phase",
    "block_type",
    "analysis_scope",
    "target_set",
    "target_pattern",
    "config_stimulus_ms",
    "config_trial_ms",
    "n_total",
    "n_valid",
    "n_anticipatory",
    "n_held_at_onset",
    "n_correct",
    "valid_accuracy",
    "target_n",
    "target_valid_n",
    "target_hits",
    "target_omissions",
    "target_hit_rate",
    "target_omission_rate",
    "near_n",
    "near_valid_n",
    "near_commissions",
    "near_commission_rate",
    "far_n",
    "far_valid_n",
    "far_commissions",
    "far_commission_rate",
    "nogo_valid_n",
    "nogo_commissions",
    "nogo_commission_rate",
    "balanced_accuracy",
    "dprime_loglinear",
    "criterion_loglinear",
    "target_rt_n",
    "target_rt_excluded_n",
    "target_rt_mean_ms",
    "target_rt_median_ms",
    "target_rt_sd_ms",
    "target_rt_iqr_ms",
    "target_rt_mad_ms",
    "target_rt_cv",
    "target_rt_min_ms",
    "target_rt_max_ms",
    "n_timing_warning",
    "n_timing_bad_gt_frame",
    "n_keyup_quality_flag",
    "n_multi_response",
    "block_duration_ms",
]

QC_FIELDS = [
    "source_session_id",
    "protocol_id",
    "subject_type",
    "subject",
    "session",
    "date",
    "session_seed",
    "target_selection_mode",
    "triplet_rank",
    "practice_set",
    "block_a_set",
    "block_a_type",
    "block_b_set",
    "block_b_type",
    "candidate_pool_size",
    "config_stimulus_ms",
    "config_trial_ms",
    "config_premature_ms",
    "schedule_rows",
    "trial_rows",
    "schedule_mismatch_count",
    "missing_trial_index_count",
    "duplicate_trial_index_count",
    "scheduled_timing_mismatch_count",
    "manifest_missing_count",
    "session_complete",
    "primary_ready",
    "press_duration_ready",
    "anticipatory_count",
    "held_key_at_onset_count",
    "timing_warning_count",
    "timing_bad_gt_frame_count",
    "max_abs_stimulus_timing_error_ms",
    "max_abs_trial_timing_error_ms",
    "keyup_quality_flag_count",
    "missing_keyup_count",
    "long_press_count",
    "multi_response_trial_count",
    "first_onset_session_ms",
    "last_end_session_ms",
    "session_span_ms",
    "refresh_hz_values",
    "stimulus_trial_frame_values",
    "config_path",
    "schedule_path",
    "trials_path",
    "qc_notes",
]


def parse_args():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_DIR / "data")
    parser.add_argument(
        "--stimulus-manifest",
        type=Path,
        default=PROJECT_DIR / "assets" / "sets" / "all_sets_manifest.csv",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent / "pipeline_config.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
    )
    return parser.parse_args()


def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1"}


def as_float(value):
    if value in (None, ""):
        return None
    return float(value)


def as_int(value):
    if value in (None, ""):
        return None
    return int(value)


def rounded(value, digits=6):
    if value is None or isinstance(value, bool):
        return value
    return round(float(value), digits)


def safe_rate(numerator, denominator):
    return numerator / denominator if denominator else None


def percentile(values, probability):
    values = sorted(values)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def mad(values):
    if not values:
        return None
    center = median(values)
    return median(abs(value - center) for value in values)


def file_hash(path):
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(PROJECT_DIR))
    except ValueError:
        return str(path)


def read_tsv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader), list(reader.fieldnames or [])


TRIAL_SCHEMA_ALIASES = {
    "overall_trial_number": "global_trial_index",
    "within_block_trial_number": "block_trial_index",
    "valid_for_analysis": "valid_for_primary",
    "too_early_response": "anticipatory",
    "press_duration": "press_duration_ms",
}


def normalize_trial_schema(raw, planned=None):
    """Expose the current acquisition schema through legacy analysis names."""
    row = dict(raw)
    for current_name, legacy_name in TRIAL_SCHEMA_ALIASES.items():
        if legacy_name not in row and current_name in row:
            row[legacy_name] = row[current_name]
    if planned:
        for field in SCHEDULE_COMPARE_FIELDS:
            if field not in row or row[field] == "":
                row[field] = planned.get(field, "")
    row.setdefault("space_held_at_onset", "0")
    row.setdefault("keyup_ms", "")
    return row


def write_tsv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    temporary.replace(path)


def protocol_id(config):
    timing = config["timing"]
    values = [
        timing["stimulus_seconds"] * 1000,
        timing["trial_seconds"] * 1000,
        timing["premature_seconds"] * 1000,
    ]

    def token(value):
        return str(int(value)) if float(value).is_integer() else str(value).replace(".", "p")

    return f"stim{token(values[0])}_trial{token(values[1])}_premature{token(values[2])}"


def discover_sessions(data_dir):
    sessions = []
    missing = []
    for trials_path in sorted(Path(data_dir).rglob("*_trials.tsv")):
        if trials_path.name.endswith("_practice_trials.tsv"):
            continue
        prefix = trials_path.name[: -len("_trials.tsv")]
        config_path = trials_path.with_name(prefix + "_config.json")
        schedule_path = trials_path.with_name(prefix + "_schedule.tsv")
        if not config_path.is_file() or not schedule_path.is_file():
            missing.append(str(trials_path))
            continue
        sessions.append(
            {
                "session_id": prefix,
                "config_path": config_path,
                "schedule_path": schedule_path,
                "trials_path": trials_path,
            }
        )
    if missing:
        raise FileNotFoundError(
            "Trials files without matching config/schedule files: " + ", ".join(missing)
        )
    if not sessions:
        raise FileNotFoundError(f"No *_trials.tsv files found below {data_dir}")
    return sessions


def load_stimulus_manifest(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapping = {}
    for row in rows:
        key = (row["set"], row["role"], row["pattern"])
        if key in mapping:
            raise ValueError(f"Duplicate stimulus manifest key: {key}")
        mapping[key] = row
    return mapping


def enrich_session(session, stimulus_manifest, settings):
    with session["config_path"].open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    schedule_rows, _ = read_tsv(session["schedule_path"])
    trial_rows, raw_fields = read_tsv(session["trials_path"])
    planned_by_index = {
        row.get("global_trial_index", ""): row
        for row in schedule_rows
    }
    trial_rows = [
        normalize_trial_schema(
            row,
            planned_by_index.get(row.get("overall_trial_number", ""), {}),
        )
        for row in trial_rows
    ]
    for field in (
        *TRIAL_SCHEMA_ALIASES.values(),
        *SCHEDULE_COMPARE_FIELDS,
        "space_held_at_onset",
        "keyup_ms",
    ):
        if field not in raw_fields:
            raw_fields.append(field)

    timing = config["timing"]
    config_stimulus_ms = float(timing["stimulus_seconds"]) * 1000
    config_trial_ms = float(timing["trial_seconds"]) * 1000
    config_premature_ms = float(timing["premature_seconds"]) * 1000
    this_protocol = protocol_id(config)
    selection = config["selection"]
    pool = selection.get("candidate_pool_allocation", {})

    schedule_mismatches = abs(len(schedule_rows) - len(trial_rows))
    for planned, actual in zip(schedule_rows, trial_rows):
        if any(planned.get(field, "") != actual.get(field, "") for field in SCHEDULE_COMPARE_FIELDS):
            schedule_mismatches += 1

    planned_indices = {as_int(row.get("global_trial_index")) for row in schedule_rows}
    actual_indices = [as_int(row.get("global_trial_index")) for row in trial_rows]
    missing_indices = planned_indices - set(actual_indices)
    duplicate_indices = len(actual_indices) - len(set(actual_indices))

    scheduled_timing_mismatches = 0
    manifest_missing = 0
    processed = []
    previous_by_block = {}
    block_sizes = Counter(row["block_index"] for row in trial_rows)

    for raw in trial_rows:
        row = dict(raw)
        stimulus_type = row["stimulus_type"]
        responded = as_bool(row["responded"])
        correct = as_bool(row["correct"])
        valid = as_bool(row["valid_for_primary"])
        phase = row["phase"]
        is_main = phase != "Practice"
        is_go = stimulus_type == "Target"
        is_nogo = not is_go

        scheduled_stimulus_ms = as_float(row.get("scheduled_stimulus_duration_ms"))
        response_window_ms = as_float(row.get("response_window_ms"))
        if (
            scheduled_stimulus_ms is None
            or response_window_ms is None
            or abs(scheduled_stimulus_ms - config_stimulus_ms) > 0.001
            or abs(response_window_ms - config_trial_ms) > 0.001
        ):
            scheduled_timing_mismatches += 1

        actual_stimulus_ms = as_float(row.get("actual_stimulus_duration_ms"))
        actual_trial_ms = as_float(row.get("actual_trial_duration_ms"))
        refresh_hz = as_float(row.get("refresh_hz"))
        frame_ms = 1000 / refresh_hz if refresh_hz else None
        stimulus_error = (
            actual_stimulus_ms - config_stimulus_ms
            if actual_stimulus_ms is not None
            else None
        )
        trial_error = (
            actual_trial_ms - config_trial_ms if actual_trial_ms is not None else None
        )
        timing_reasons = []
        warning_threshold = float(settings["timing_warning_ms"])
        if stimulus_error is None or trial_error is None:
            timing_reasons.append("missing_actual_timing")
        else:
            if abs(stimulus_error) > warning_threshold:
                timing_reasons.append("stimulus_abs_error_gt_warning")
            if abs(trial_error) > warning_threshold:
                timing_reasons.append("trial_abs_error_gt_warning")
        timing_warning = bool(timing_reasons)
        bad_threshold = (
            frame_ms * float(settings["timing_bad_frame_multiplier"])
            if frame_ms is not None
            else None
        )
        timing_bad = (
            bad_threshold is None
            or stimulus_error is None
            or trial_error is None
            or abs(stimulus_error) > bad_threshold
            or abs(trial_error) > bad_threshold
        )

        keyup_reasons = []
        if responded:
            press_duration_ms = as_float(row.get("press_duration_ms"))
            if press_duration_ms is None:
                keyup_reasons.append("missing_keyup_or_duration")
            elif press_duration_ms < 0:
                keyup_reasons.append("negative_press_duration")
            elif press_duration_ms > config_trial_ms * float(
                settings["press_duration_max_response_window_multiplier"]
            ):
                keyup_reasons.append("press_duration_exceeds_response_window")

        manifest_key = (row["target_set"], stimulus_type, row["stimulus_pattern"])
        stimulus = stimulus_manifest.get(manifest_key)
        if stimulus is None:
            manifest_missing += 1

        block_key = row["block_index"]
        previous = previous_by_block.get(block_key)
        block_trial_index = as_int(row["block_trial_index"]) or 0
        block_size = block_sizes[block_key]
        quartile = min(4, max(1, ((block_trial_index - 1) * 4) // block_size + 1))

        rt_ms = as_float(row.get("rt_ms"))
        response_limit = response_window_ms if response_window_ms is not None else config_trial_ms
        rt_eligible = (
            is_main
            and valid
            and is_go
            and correct
            and rt_ms is not None
            and config_premature_ms <= rt_ms < response_limit
        )

        row.update(
            {
                "source_session_id": session["session_id"],
                "source_trials_file": display_path(session["trials_path"]),
                "protocol_id": this_protocol,
                "config_stimulus_ms": rounded(config_stimulus_ms),
                "config_trial_ms": rounded(config_trial_ms),
                "config_premature_ms": rounded(config_premature_ms),
                "candidate_pool_size": pool.get("pool_size", ""),
                "candidate_pool_maximum": pool.get("maximum_pool_size", ""),
                "stimulus_manifest_joined": stimulus is not None,
                "stimulus_rank": stimulus.get("rank", "") if stimulus else "",
                "is_main": is_main,
                "is_go": is_go,
                "is_nogo": is_nogo,
                "hit": is_go and valid and responded,
                "omission": is_go and valid and not responded,
                "commission": is_nogo and valid and responded,
                "correct_rejection": is_nogo and valid and not responded,
                "frame_ms": rounded(frame_ms),
                "stimulus_timing_error_ms": rounded(stimulus_error),
                "trial_timing_error_ms": rounded(trial_error),
                "timing_warning": timing_warning,
                "timing_bad_gt_frame": timing_bad,
                "timing_flag_reasons": "|".join(timing_reasons),
                "keyup_quality_flag": bool(keyup_reasons),
                "keyup_quality_reasons": "|".join(keyup_reasons),
                "primary_include": is_main and valid,
                "rt_eligible": rt_eligible,
                "prev_stimulus_type": previous["stimulus_type"] if previous else "",
                "prev_responded": previous["responded"] if previous else "",
                "prev_correct": previous["correct"] if previous else "",
                "prev_error_type": previous["error_type"] if previous else "",
                "prev_rt_ms": previous["rt_ms"] if previous else "",
                "post_error": (
                    bool(previous)
                    and previous.get("correct", "") not in ("", None)
                    and not as_bool(previous["correct"])
                ),
                "post_nogo": bool(previous) and previous["stimulus_type"] != "Target",
                "stimulus_switch": bool(previous)
                and previous["stimulus_type"] != stimulus_type,
                "trial_quartile": quartile,
                "time_on_task_fraction": rounded(block_trial_index / block_size),
                "rt_group_median_ms": "",
                "rt_group_mad_ms": "",
                "rt_outlier_mad": False,
                "rt_include_strict": False,
            }
        )
        for field in STIMULUS_METRIC_FIELDS:
            row[f"stimulus_{field}"] = stimulus.get(field, "") if stimulus else ""

        processed.append(row)
        previous_by_block[block_key] = raw

    rt_groups = defaultdict(list)
    for row in processed:
        if as_bool(row["rt_eligible"]) and not as_bool(row["timing_bad_gt_frame"]):
            rt_groups[(row["source_session_id"], row["block_type"])].append(
                as_float(row["rt_ms"])
            )

    group_stats = {}
    for key, values in rt_groups.items():
        clean_values = [value for value in values if value is not None]
        group_stats[key] = (median(clean_values), mad(clean_values), len(clean_values))

    for row in processed:
        key = (row["source_session_id"], row["block_type"])
        center, dispersion, count = group_stats.get(key, (None, None, 0))
        row["rt_group_median_ms"] = rounded(center)
        row["rt_group_mad_ms"] = rounded(dispersion)
        rt_value = as_float(row.get("rt_ms"))
        is_outlier = False
        if (
            as_bool(row["rt_eligible"])
            and center is not None
            and dispersion not in (None, 0)
            and count >= int(settings["rt_outlier_min_trials"])
        ):
            robust_sd = 1.4826 * dispersion
            is_outlier = abs(rt_value - center) > float(
                settings["rt_outlier_mad_multiplier"]
            ) * robust_sd
        row["rt_outlier_mad"] = is_outlier
        strict = as_bool(row["rt_eligible"])
        if settings["exclude_timing_bad_from_strict_rt"]:
            strict = strict and not as_bool(row["timing_bad_gt_frame"])
        if settings["exclude_rt_outliers_from_strict_rt"]:
            strict = strict and not is_outlier
        row["rt_include_strict"] = strict

    actual_stimulus_errors = [
        abs(as_float(row["stimulus_timing_error_ms"]))
        for row in processed
        if as_float(row["stimulus_timing_error_ms"]) is not None
    ]
    actual_trial_errors = [
        abs(as_float(row["trial_timing_error_ms"]))
        for row in processed
        if as_float(row["trial_timing_error_ms"]) is not None
    ]
    onset_values = [as_float(row.get("onset_session_ms")) for row in processed]
    onset_values = [value for value in onset_values if value is not None]
    last_end = None
    if processed:
        last_onset = as_float(processed[-1].get("onset_session_ms"))
        last_duration = as_float(processed[-1].get("actual_trial_duration_ms"))
        if last_onset is not None and last_duration is not None:
            last_end = last_onset + last_duration

    missing_keyup_count = sum(
        as_bool(row["responded"]) and as_float(row.get("keyup_ms")) is None
        for row in processed
    )
    long_press_count = sum(
        as_float(row.get("press_duration_ms")) is not None
        and as_float(row["press_duration_ms"]) > config_trial_ms
        for row in processed
    )
    refresh_values = sorted({row.get("refresh_hz", "") for row in processed})
    frame_values = sorted(
        {f"{row.get('stimulus_frames', '')}/{row.get('trial_frames', '')}" for row in processed}
    )
    notes = []
    if schedule_mismatches:
        notes.append("schedule_trial_mismatch")
    if missing_indices:
        notes.append("missing_trial_indices")
    if duplicate_indices:
        notes.append("duplicate_trial_indices")
    if scheduled_timing_mismatches:
        notes.append("config_row_scheduled_timing_mismatch")
    if manifest_missing:
        notes.append("stimulus_manifest_join_failed")
    if any(as_bool(row["keyup_quality_flag"]) for row in processed):
        notes.append("keyup_or_press_duration_not_ready")
    if any(as_bool(row.get("space_held_at_onset")) for row in processed):
        notes.append("space_held_at_stimulus_onset")

    session_complete = (
        len(schedule_rows) == len(trial_rows)
        and not schedule_mismatches
        and not missing_indices
        and not duplicate_indices
    )
    qc = {
        "source_session_id": session["session_id"],
        "protocol_id": this_protocol,
        "subject_type": config["subject"]["SubType"],
        "subject": config["subject"]["SubIdx"],
        "session": config["subject"]["SubSes"],
        "date": config["subject"]["date"],
        "session_seed": config["session_seed"],
        "target_selection_mode": config["target_selection_mode"],
        "triplet_rank": selection.get("triplet_rank", ""),
        "practice_set": selection.get(
            "practice_set",
            "|".join(selection.get("practice_sets", [])),
        ),
        "block_a_set": selection["block_a_set"],
        "block_a_type": selection["block_a_type"],
        "block_b_set": selection["block_b_set"],
        "block_b_type": selection["block_b_type"],
        "candidate_pool_size": pool.get("pool_size", ""),
        "config_stimulus_ms": rounded(config_stimulus_ms),
        "config_trial_ms": rounded(config_trial_ms),
        "config_premature_ms": rounded(config_premature_ms),
        "schedule_rows": len(schedule_rows),
        "trial_rows": len(trial_rows),
        "schedule_mismatch_count": schedule_mismatches,
        "missing_trial_index_count": len(missing_indices),
        "duplicate_trial_index_count": duplicate_indices,
        "scheduled_timing_mismatch_count": scheduled_timing_mismatches,
        "manifest_missing_count": manifest_missing,
        "session_complete": session_complete,
        "primary_ready": session_complete and not manifest_missing,
        "press_duration_ready": not any(
            as_bool(row["keyup_quality_flag"]) for row in processed
        ),
        "anticipatory_count": sum(as_bool(row["anticipatory"]) for row in processed),
        "held_key_at_onset_count": sum(
            as_bool(row.get("space_held_at_onset")) for row in processed
        ),
        "timing_warning_count": sum(as_bool(row["timing_warning"]) for row in processed),
        "timing_bad_gt_frame_count": sum(
            as_bool(row["timing_bad_gt_frame"]) for row in processed
        ),
        "max_abs_stimulus_timing_error_ms": rounded(
            max(actual_stimulus_errors) if actual_stimulus_errors else None
        ),
        "max_abs_trial_timing_error_ms": rounded(
            max(actual_trial_errors) if actual_trial_errors else None
        ),
        "keyup_quality_flag_count": sum(
            as_bool(row["keyup_quality_flag"]) for row in processed
        ),
        "missing_keyup_count": missing_keyup_count,
        "long_press_count": long_press_count,
        "multi_response_trial_count": sum(
            (as_int(row.get("response_count")) or 0) > 1 for row in processed
        ),
        "first_onset_session_ms": rounded(min(onset_values) if onset_values else None),
        "last_end_session_ms": rounded(last_end),
        "session_span_ms": rounded(
            last_end - min(onset_values)
            if last_end is not None and onset_values
            else None
        ),
        "refresh_hz_values": "|".join(refresh_values),
        "stimulus_trial_frame_values": "|".join(frame_values),
        "config_path": display_path(session["config_path"]),
        "schedule_path": display_path(session["schedule_path"]),
        "trials_path": display_path(session["trials_path"]),
        "qc_notes": "|".join(notes),
    }
    return processed, raw_fields, qc, config


def signal_detection(target_hits, target_n, false_alarms, nogo_n):
    if not target_n or not nogo_n:
        return None, None
    hit_rate = (target_hits + 0.5) / (target_n + 1)
    false_alarm_rate = (false_alarms + 0.5) / (nogo_n + 1)
    normal = NormalDist()
    z_hit = normal.inv_cdf(hit_rate)
    z_false_alarm = normal.inv_cdf(false_alarm_rate)
    return z_hit - z_false_alarm, -0.5 * (z_hit + z_false_alarm)


def rt_statistics(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return {field: None for field in ("n", "mean", "median", "sd", "iqr", "mad", "cv", "min", "max")}
    average = mean(values)
    deviation = stdev(values) if len(values) > 1 else None
    return {
        "n": len(values),
        "mean": average,
        "median": median(values),
        "sd": deviation,
        "iqr": percentile(values, 0.75) - percentile(values, 0.25),
        "mad": mad(values),
        "cv": deviation / average if deviation is not None and average else None,
        "min": min(values),
        "max": max(values),
    }


def build_participant_summary(processed_rows):
    groups = defaultdict(list)
    for row in processed_rows:
        groups[(row["source_session_id"], row["block_index"])].append(row)

    output = []
    for _, rows in sorted(groups.items(), key=lambda item: (item[0][0], int(item[0][1]))):
        first = rows[0]
        valid = [row for row in rows if as_bool(row["valid_for_primary"])]
        target_all = [row for row in rows if row["stimulus_type"] == "Target"]
        target = [row for row in valid if row["stimulus_type"] == "Target"]
        near_all = [row for row in rows if row["stimulus_type"] == "Near"]
        near = [row for row in valid if row["stimulus_type"] == "Near"]
        far_all = [row for row in rows if row["stimulus_type"] == "Far"]
        far = [row for row in valid if row["stimulus_type"] == "Far"]
        nogo = near + far
        target_hits = sum(as_bool(row["responded"]) for row in target)
        near_commissions = sum(as_bool(row["responded"]) for row in near)
        far_commissions = sum(as_bool(row["responded"]) for row in far)
        nogo_commissions = near_commissions + far_commissions
        dprime, criterion = signal_detection(
            target_hits, len(target), nogo_commissions, len(nogo)
        )
        hit_rate = safe_rate(target_hits, len(target))
        false_alarm_rate = safe_rate(nogo_commissions, len(nogo))
        balanced_accuracy = (
            (hit_rate + (1 - false_alarm_rate)) / 2
            if hit_rate is not None and false_alarm_rate is not None
            else None
        )
        strict_rts = [
            as_float(row.get("rt_ms"))
            for row in rows
            if as_bool(row["rt_include_strict"])
        ]
        rt_stats = rt_statistics(strict_rts)
        eligible_rt_count = sum(as_bool(row["rt_eligible"]) for row in rows)
        onset_values = [as_float(row.get("onset_session_ms")) for row in rows]
        onset_values = [value for value in onset_values if value is not None]
        last = rows[-1]
        last_end = (
            as_float(last.get("onset_session_ms"))
            + as_float(last.get("actual_trial_duration_ms"))
            if as_float(last.get("onset_session_ms")) is not None
            and as_float(last.get("actual_trial_duration_ms")) is not None
            else None
        )
        block_duration = (
            last_end - min(onset_values)
            if last_end is not None and onset_values
            else None
        )

        output.append(
            {
                "source_session_id": first["source_session_id"],
                "protocol_id": first["protocol_id"],
                "subject_type": first["subject_type"],
                "subject": first["subject"],
                "session": first["session"],
                "date": first["date"],
                "session_seed": first["session_seed"],
                "block_index": first["block_index"],
                "phase": first["phase"],
                "block_type": first["block_type"],
                "analysis_scope": "practice" if first["phase"] == "Practice" else "primary",
                "target_set": first["target_set"],
                "target_pattern": first["target_pattern"],
                "config_stimulus_ms": first["config_stimulus_ms"],
                "config_trial_ms": first["config_trial_ms"],
                "n_total": len(rows),
                "n_valid": len(valid),
                "n_anticipatory": sum(as_bool(row["anticipatory"]) for row in rows),
                "n_held_at_onset": sum(
                    as_bool(row.get("space_held_at_onset")) for row in rows
                ),
                "n_correct": sum(as_bool(row["correct"]) for row in valid),
                "valid_accuracy": rounded(
                    safe_rate(sum(as_bool(row["correct"]) for row in valid), len(valid))
                ),
                "target_n": len(target_all),
                "target_valid_n": len(target),
                "target_hits": target_hits,
                "target_omissions": len(target) - target_hits,
                "target_hit_rate": rounded(hit_rate),
                "target_omission_rate": rounded(
                    safe_rate(len(target) - target_hits, len(target))
                ),
                "near_n": len(near_all),
                "near_valid_n": len(near),
                "near_commissions": near_commissions,
                "near_commission_rate": rounded(
                    safe_rate(near_commissions, len(near))
                ),
                "far_n": len(far_all),
                "far_valid_n": len(far),
                "far_commissions": far_commissions,
                "far_commission_rate": rounded(
                    safe_rate(far_commissions, len(far))
                ),
                "nogo_valid_n": len(nogo),
                "nogo_commissions": nogo_commissions,
                "nogo_commission_rate": rounded(false_alarm_rate),
                "balanced_accuracy": rounded(balanced_accuracy),
                "dprime_loglinear": rounded(dprime),
                "criterion_loglinear": rounded(criterion),
                "target_rt_n": rt_stats["n"] or 0,
                "target_rt_excluded_n": eligible_rt_count - (rt_stats["n"] or 0),
                "target_rt_mean_ms": rounded(rt_stats["mean"]),
                "target_rt_median_ms": rounded(rt_stats["median"]),
                "target_rt_sd_ms": rounded(rt_stats["sd"]),
                "target_rt_iqr_ms": rounded(rt_stats["iqr"]),
                "target_rt_mad_ms": rounded(rt_stats["mad"]),
                "target_rt_cv": rounded(rt_stats["cv"]),
                "target_rt_min_ms": rounded(rt_stats["min"]),
                "target_rt_max_ms": rounded(rt_stats["max"]),
                "n_timing_warning": sum(as_bool(row["timing_warning"]) for row in rows),
                "n_timing_bad_gt_frame": sum(
                    as_bool(row["timing_bad_gt_frame"]) for row in rows
                ),
                "n_keyup_quality_flag": sum(
                    as_bool(row["keyup_quality_flag"]) for row in rows
                ),
                "n_multi_response": sum(
                    (as_int(row.get("response_count")) or 0) > 1 for row in rows
                ),
                "block_duration_ms": rounded(block_duration),
            }
        )
    return output


def build_contrasts(summary_rows):
    by_session = defaultdict(dict)
    for row in summary_rows:
        if row["block_type"] in ("Heavy-go", "Low-go"):
            by_session[row["source_session_id"]][row["block_type"]] = row

    metric_names = [
        "valid_accuracy",
        "balanced_accuracy",
        "target_hit_rate",
        "near_commission_rate",
        "far_commission_rate",
        "nogo_commission_rate",
        "dprime_loglinear",
        "criterion_loglinear",
        "target_rt_mean_ms",
        "target_rt_median_ms",
        "target_rt_sd_ms",
        "target_rt_cv",
    ]
    fields = [
        "source_session_id",
        "protocol_id",
        "subject_type",
        "subject",
        "session",
        "date",
        "block_order",
        "heavy_block_index",
        "low_block_index",
    ]
    for metric in metric_names:
        fields.extend([f"heavy_{metric}", f"low_{metric}", f"delta_heavy_minus_low_{metric}"])

    output = []
    for session_id, blocks in sorted(by_session.items()):
        if set(blocks) != {"Heavy-go", "Low-go"}:
            continue
        heavy = blocks["Heavy-go"]
        low = blocks["Low-go"]
        ordered = sorted([heavy, low], key=lambda row: int(row["block_index"]))
        row = {
            "source_session_id": session_id,
            "protocol_id": heavy["protocol_id"],
            "subject_type": heavy["subject_type"],
            "subject": heavy["subject"],
            "session": heavy["session"],
            "date": heavy["date"],
            "block_order": "_then_".join(item["block_type"] for item in ordered),
            "heavy_block_index": heavy["block_index"],
            "low_block_index": low["block_index"],
        }
        for metric in metric_names:
            heavy_value = as_float(heavy.get(metric))
            low_value = as_float(low.get(metric))
            row[f"heavy_{metric}"] = rounded(heavy_value)
            row[f"low_{metric}"] = rounded(low_value)
            row[f"delta_heavy_minus_low_{metric}"] = rounded(
                heavy_value - low_value
                if heavy_value is not None and low_value is not None
                else None
            )
        output.append(row)
    return output, fields


def build_stimulus_summary(processed_rows):
    groups = defaultdict(list)
    for row in processed_rows:
        if as_bool(row["is_main"]):
            key = (
                row["protocol_id"],
                row["block_type"],
                row["target_set"],
                row["target_pattern"],
                row["stimulus_type"],
                row["stimulus_pattern"],
            )
            groups[key].append(row)

    metric_fields = [f"stimulus_{field}" for field in STIMULUS_METRIC_FIELDS]
    fields = [
        "protocol_id",
        "block_type",
        "target_set",
        "target_pattern",
        "stimulus_type",
        "stimulus_pattern",
        "stimulus_rank",
        *metric_fields,
        "n_subjects",
        "n_sessions",
        "n_trials",
        "n_valid",
        "n_responded",
        "response_rate",
        "n_correct",
        "accuracy",
        "rt_n",
        "rt_mean_ms",
        "rt_median_ms",
    ]
    output = []
    for key, rows in sorted(groups.items()):
        first = rows[0]
        valid = [row for row in rows if as_bool(row["valid_for_primary"])]
        rts = [
            as_float(row.get("rt_ms"))
            for row in valid
            if as_bool(row["responded"]) and as_float(row.get("rt_ms")) is not None
        ]
        row = {
            "protocol_id": key[0],
            "block_type": key[1],
            "target_set": key[2],
            "target_pattern": key[3],
            "stimulus_type": key[4],
            "stimulus_pattern": key[5],
            "stimulus_rank": first["stimulus_rank"],
            "n_subjects": len({item["subject"] for item in rows}),
            "n_sessions": len({item["source_session_id"] for item in rows}),
            "n_trials": len(rows),
            "n_valid": len(valid),
            "n_responded": sum(as_bool(item["responded"]) for item in valid),
            "response_rate": rounded(
                safe_rate(sum(as_bool(item["responded"]) for item in valid), len(valid))
            ),
            "n_correct": sum(as_bool(item["correct"]) for item in valid),
            "accuracy": rounded(
                safe_rate(sum(as_bool(item["correct"]) for item in valid), len(valid))
            ),
            "rt_n": len(rts),
            "rt_mean_ms": rounded(mean(rts) if rts else None),
            "rt_median_ms": rounded(median(rts) if rts else None),
        }
        for field in metric_fields:
            row[field] = first[field]
        output.append(row)
    return output, fields


def build_sequence_summary(processed_rows):
    groups = defaultdict(list)
    for row in processed_rows:
        if not as_bool(row["is_main"]):
            continue
        sequence_role = "minority" if as_bool(row["is_minority"]) else "dominant"
        key = (
            row["source_session_id"],
            row["protocol_id"],
            row["block_type"],
            sequence_role,
            row["stimulus_type"],
            row["dominant_run_length"],
            row["position_in_dominant_run"],
        )
        groups[key].append(row)
    fields = [
        "source_session_id",
        "protocol_id",
        "subject_type",
        "subject",
        "session",
        "block_type",
        "sequence_role",
        "stimulus_type",
        "dominant_run_length",
        "position_in_dominant_run",
        "n_trials",
        "n_valid",
        "n_responded",
        "response_rate",
        "n_correct",
        "accuracy",
        "rt_n",
        "rt_mean_ms",
        "rt_median_ms",
    ]
    output = []
    for key, rows in sorted(groups.items()):
        first = rows[0]
        valid = [row for row in rows if as_bool(row["valid_for_primary"])]
        rts = [
            as_float(row.get("rt_ms"))
            for row in valid
            if as_bool(row["responded"]) and as_float(row.get("rt_ms")) is not None
        ]
        output.append(
            {
                "source_session_id": key[0],
                "protocol_id": key[1],
                "subject_type": first["subject_type"],
                "subject": first["subject"],
                "session": first["session"],
                "block_type": key[2],
                "sequence_role": key[3],
                "stimulus_type": key[4],
                "dominant_run_length": key[5],
                "position_in_dominant_run": key[6],
                "n_trials": len(rows),
                "n_valid": len(valid),
                "n_responded": sum(as_bool(item["responded"]) for item in valid),
                "response_rate": rounded(
                    safe_rate(sum(as_bool(item["responded"]) for item in valid), len(valid))
                ),
                "n_correct": sum(as_bool(item["correct"]) for item in valid),
                "accuracy": rounded(
                    safe_rate(sum(as_bool(item["correct"]) for item in valid), len(valid))
                ),
                "rt_n": len(rts),
                "rt_mean_ms": rounded(mean(rts) if rts else None),
                "rt_median_ms": rounded(median(rts) if rts else None),
            }
        )
    return output, fields


def main():
    args = parse_args()
    with args.config.open("r", encoding="utf-8") as handle:
        settings = json.load(handle)
    sessions = discover_sessions(args.data_dir)
    stimulus_manifest = load_stimulus_manifest(args.stimulus_manifest)

    all_processed = []
    raw_fields = []
    raw_field_set = set()
    raw_schema_counts = Counter()
    qc_rows = []
    configs = []
    input_paths = [args.config, args.stimulus_manifest]
    for session in sessions:
        processed, fields, qc, config = enrich_session(
            session, stimulus_manifest, settings
        )
        raw_schema_counts[tuple(fields)] += 1
        for field in fields:
            if field not in raw_field_set:
                raw_fields.append(field)
                raw_field_set.add(field)
        all_processed.extend(processed)
        qc_rows.append(qc)
        configs.append(config)
        input_paths.extend(
            [session["config_path"], session["schedule_path"], session["trials_path"]]
        )

    participant_summary = build_participant_summary(all_processed)
    participant_contrasts, contrast_fields = build_contrasts(participant_summary)
    stimulus_summary, stimulus_fields = build_stimulus_summary(all_processed)
    sequence_summary, sequence_fields = build_sequence_summary(all_processed)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_specs = [
        (
            "processed_trials.tsv",
            all_processed,
            list(raw_fields or []) + DERIVED_TRIAL_FIELDS,
        ),
        ("participant_summary.tsv", participant_summary, SUMMARY_FIELDS),
        ("participant_contrasts.tsv", participant_contrasts, contrast_fields),
        ("session_qc.tsv", qc_rows, QC_FIELDS),
        ("stimulus_summary.tsv", stimulus_summary, stimulus_fields),
        ("sequence_summary.tsv", sequence_summary, sequence_fields),
    ]
    for filename, rows, fields in output_specs:
        write_tsv(args.output_dir / filename, rows, fields)

    protocol_counts = Counter(row["protocol_id"] for row in qc_rows)
    warnings = []
    if len(raw_schema_counts) > 1:
        warnings.append(
            "Multiple raw trial schemas are present. The processed trial table "
            "uses their ordered union and fills unavailable legacy fields with blanks."
        )
    if len(protocol_counts) > 1:
        warnings.append(
            "Multiple timing protocols are present. Do not pool sessions without "
            "stratifying or modelling protocol_id."
        )
    for row in qc_rows:
        if not as_bool(row["primary_ready"]):
            warnings.append(
                f"{row['source_session_id']}: primary_ready=False; inspect session_qc.tsv"
            )
        if not as_bool(row["press_duration_ready"]):
            warnings.append(
                f"{row['source_session_id']}: keyup/press-duration fields are not analysis-ready."
            )

    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_dir": str(PROJECT_DIR),
        "settings": settings,
        "session_count": len(sessions),
        "processed_trial_count": len(all_processed),
        "protocol_counts": dict(sorted(protocol_counts.items())),
        "warnings": warnings,
        "inputs": [
            {
                "path": str(Path(path).resolve()),
                "sha256": file_hash(path),
            }
            for path in sorted(set(input_paths), key=lambda value: str(value))
        ],
        "outputs": [
            {
                "path": str((args.output_dir / filename).resolve()),
                "rows": len(rows),
                "sha256": file_hash(args.output_dir / filename),
            }
            for filename, rows, _ in output_specs
        ],
    }
    write_json(args.output_dir / "analysis_manifest.json", manifest)

    print(f"sessions={len(sessions)}")
    print(f"processed_trials={len(all_processed)}")
    print(f"participant_summary_rows={len(participant_summary)}")
    print(f"participant_contrast_rows={len(participant_contrasts)}")
    print(f"protocols={dict(sorted(protocol_counts.items()))}")
    print(f"output_dir={args.output_dir.resolve()}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
