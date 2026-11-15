# -*- coding: utf-8 -*-

from collections import Counter, defaultdict
from pathlib import Path
import csv
import re


PRACTICE = "Practice"
HEAVY_GO = "Heavy-go"
LOW_GO = "Low-go"

TARGET = "Target"
NEAR = "Near"
FAR = "Far"

PRACTICE_TRIAL_COUNT = 15
MAX_PRACTICE_ATTEMPTS = 3
MAIN_TRIAL_COUNT = 150

PRACTICE_COUNTS = {TARGET: 5, NEAR: 5, FAR: 5}
HEAVY_GO_COUNTS = {TARGET: 112, NEAR: 19, FAR: 19}
LOW_GO_COUNTS = {TARGET: 19, NEAR: 19, FAR: 112}

MAX_RUN_LENGTH = 4
MAX_IDENTICAL_RUN_LENGTH_CHOICES = 2
MAX_IDENTICAL_MINORITY_CHOICES = 3

PATTERN_RE = re.compile(r"^([01]{9})_")
CANDIDATE_RANK_RE = re.compile(r"_(?:Near|Far)_(\d+)\.png$", re.IGNORECASE)
ALL_PATTERNS = tuple(
    f"{value:09b}"
    for value in range(2 ** 9)
    if f"{value:09b}".count("1") == 3
)
PATTERN_ID_BY_BINARY = {
    pattern: index
    for index, pattern in enumerate(ALL_PATTERNS, start=1)
}


def pattern_from_path(path):
    match = PATTERN_RE.match(Path(path).name)
    if not match:
        raise ValueError(f"Cannot read a 9-bit pattern from: {path}")
    return match.group(1)


def pattern_id(pattern):
    try:
        return PATTERN_ID_BY_BINARY[pattern]
    except KeyError as exc:
        raise ValueError(f"Unknown 3-of-9 pattern: {pattern}") from exc


def load_set_catalog(sets_dir):
    sets_dir = Path(sets_dir)
    if not sets_dir.exists():
        raise FileNotFoundError(f"Set directory not found: {sets_dir}")

    catalog = []
    for set_dir in sorted(sets_dir.glob("set[0-9][0-9]")):
        targets = sorted((set_dir / TARGET).glob("*.png"))
        near = sorted((set_dir / NEAR).glob("*.png"))
        far = sorted((set_dir / FAR).glob("*.png"))
        if len(targets) != 1:
            raise ValueError(
                f"{set_dir.name}: expected one Target image, found {len(targets)}"
            )
        if not near or not far:
            raise ValueError(f"{set_dir.name}: Near and Far folders must not be empty")

        catalog.append({
            "set_name": set_dir.name,
            "set_dir": set_dir,
            "target_path": targets[0],
            "target_pattern": pattern_from_path(targets[0]),
            "near_paths": near,
            "far_paths": far,
        })

    if len(catalog) < 3:
        raise ValueError(f"At least three set folders are required; found {len(catalog)}")
    return catalog


def select_target_sets(
    catalog,
    rng,
    target_selection_mode,
    top_combination_pool,
    triplet_ranking_path,
):
    catalog_by_name = {item["set_name"]: item for item in catalog}

    if target_selection_mode == 0:
        selected = rng.sample(catalog, 3)
        triplet_rank = ""
    elif target_selection_mode == 1:
        triplet_ranking_path = Path(triplet_ranking_path)
        if not triplet_ranking_path.exists():
            raise FileNotFoundError(
                f"Triplet ranking file not found: {triplet_ranking_path}"
            )
        with triplet_ranking_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        usable = rows[: min(top_combination_pool, len(rows))]
        if not usable:
            raise ValueError("The ranked Target triplet file is empty")
        chosen = rng.choice(usable)
        selected = [
            catalog_by_name[chosen["target_1_set"]],
            catalog_by_name[chosen["target_2_set"]],
            catalog_by_name[chosen["target_3_set"]],
        ]
        triplet_rank = chosen.get("rank", "")
    else:
        raise ValueError("target_selection_mode must be 0 or 1")

    selected = [
        dict(
            item,
            near_paths=list(item["near_paths"]),
            far_paths=list(item["far_paths"]),
        )
        for item in selected
    ]
    rng.shuffle(selected)
    return selected, triplet_rank


def candidate_rank(path):
    match = CANDIDATE_RANK_RE.search(Path(path).name)
    return int(match.group(1)) if match else 9999


def match_candidate_pools(pool_paths, quota):
    """Give every pool `quota` exact patterns, with global one-pattern ownership."""
    path_by_slot_pattern = {
        slot: {pattern_from_path(path): path for path in paths}
        for slot, paths in pool_paths.items()
    }
    candidates = {
        slot: sorted(
            paths_by_pattern,
            key=lambda pattern: (
                candidate_rank(paths_by_pattern[pattern]),
                pattern,
            ),
        )
        for slot, paths_by_pattern in path_by_slot_pattern.items()
    }
    slot_copies = [
        (slot, copy_index)
        for slot in sorted(candidates, key=lambda key: len(candidates[key]))
        for copy_index in range(quota)
    ]
    pattern_owner = {}

    def assign(slot_copy, seen_patterns):
        slot, _ = slot_copy
        for pattern in candidates[slot]:
            if pattern in seen_patterns:
                continue
            seen_patterns.add(pattern)
            previous_owner = pattern_owner.get(pattern)
            if previous_owner is None or assign(previous_owner, seen_patterns):
                pattern_owner[pattern] = slot_copy
                return True
        return False

    for slot_copy in slot_copies:
        if not assign(slot_copy, set()):
            return None

    allocated = {slot: [] for slot in pool_paths}
    for pattern, (slot, _) in pattern_owner.items():
        allocated[slot].append(path_by_slot_pattern[slot][pattern])
    for slot in allocated:
        allocated[slot].sort(key=lambda path: (candidate_rank(path), path.name))
    return allocated


def allocate_balanced_candidate_pools(
    selected_sets,
    balanced_pool_size=None,
    forbidden_patterns=None,
):
    """Resolve all exact-pattern overlaps while keeping six pool sizes equal."""
    selected_target_patterns = {item["target_pattern"] for item in selected_sets}
    forbidden_patterns = set(forbidden_patterns or ()) | selected_target_patterns
    pool_paths = {}
    eligibility = defaultdict(set)

    for item in selected_sets:
        for role, source_key in ((NEAR, "near_paths"), (FAR, "far_paths")):
            slot = (item["set_name"], role)
            paths = [
                path
                for path in item[source_key]
                if pattern_from_path(path) not in forbidden_patterns
            ]
            if not paths:
                raise ValueError(f"{item['set_name']} has no usable {role} candidates")
            pool_paths[slot] = paths
            for path in paths:
                eligibility[pattern_from_path(path)].add(slot)

    upper_bound = min(
        min(len(paths) for paths in pool_paths.values()),
        len(eligibility) // len(pool_paths),
    )
    maximum_quota = 0
    maximum_allocation = None
    for quota in range(upper_bound, 0, -1):
        allocation = match_candidate_pools(pool_paths, quota)
        if allocation is not None:
            maximum_quota = quota
            maximum_allocation = allocation
            break
    if maximum_allocation is None:
        raise ValueError("Could not allocate one unique candidate to every Near/Far pool")

    requested_quota = (
        maximum_quota if balanced_pool_size is None else balanced_pool_size
    )
    if requested_quota < 1 or requested_quota > maximum_quota:
        raise ValueError(
            f"balanced_pool_size={requested_quota} is unavailable; "
            f"maximum is {maximum_quota}"
        )
    allocation = (
        maximum_allocation
        if requested_quota == maximum_quota
        else match_candidate_pools(pool_paths, requested_quota)
    )

    for item in selected_sets:
        item["near_paths"] = allocation[(item["set_name"], NEAR)]
        item["far_paths"] = allocation[(item["set_name"], FAR)]

    overlaps = sorted(
        pattern for pattern, slots in eligibility.items() if len(slots) > 1
    )
    return {
        "pool_size": requested_quota,
        "maximum_pool_size": maximum_quota,
        "overlap_count_before_allocation": len(overlaps),
        "overlap_patterns_before_allocation": overlaps,
    }


def has_run_longer_than(values, maximum):
    previous = None
    current = 0
    for value in values:
        current = current + 1 if value == previous else 1
        if current > maximum:
            return True
        previous = value
    return False


def constrained_shuffle(values, maximum_repeat, rng, max_attempts=10000):
    values = list(values)
    for _ in range(max_attempts):
        candidate = list(values)
        rng.shuffle(candidate)
        if not has_run_longer_than(candidate, maximum_repeat):
            return candidate
    raise RuntimeError("Could not create a constrained shuffle")


def make_dominant_run_lengths(rng, run_count=38, dominant_count=112):
    for _ in range(10000):
        lengths = []
        remaining = dominant_count

        for position in range(run_count):
            remaining_slots = run_count - position - 1
            valid = []
            for length in range(1, MAX_RUN_LENGTH + 1):
                remainder = remaining - length
                if not remaining_slots <= remainder <= remaining_slots * MAX_RUN_LENGTH:
                    continue
                if (
                    len(lengths) >= MAX_IDENTICAL_RUN_LENGTH_CHOICES
                    and all(
                        previous == length
                        for previous in lengths[-MAX_IDENTICAL_RUN_LENGTH_CHOICES:]
                    )
                ):
                    continue
                valid.append(length)

            if not valid:
                break
            chosen = rng.choice(valid)
            lengths.append(chosen)
            remaining -= chosen

        if len(lengths) == run_count and remaining == 0:
            return lengths

    raise RuntimeError("Could not create the constrained dominant run lengths")


def make_practice_trials(rng):
    counts = dict(PRACTICE_COUNTS)
    types = [
        stimulus_type
        for stimulus_type, count in counts.items()
        for _ in range(count)
    ]
    types = constrained_shuffle(types, maximum_repeat=3, rng=rng)

    trials = []
    for stimulus_type in types:
        trials.append({
            "stimulus_type": stimulus_type,
            "is_minority": stimulus_type != TARGET,
            "dominant_run_index": "",
            "dominant_run_length": "",
            "position_in_dominant_run": "",
        })
    return trials, counts


def make_main_block_trials(block_type, rng):
    if block_type == HEAVY_GO:
        dominant_type = TARGET
        minority_types = [NEAR] * 19 + [FAR] * 19
        expected_counts = HEAVY_GO_COUNTS
    elif block_type == LOW_GO:
        dominant_type = FAR
        minority_types = [TARGET] * 19 + [NEAR] * 19
        expected_counts = LOW_GO_COUNTS
    else:
        raise ValueError(f"Unknown block type: {block_type}")

    run_lengths = make_dominant_run_lengths(rng)
    minority_types = constrained_shuffle(
        minority_types,
        maximum_repeat=MAX_IDENTICAL_MINORITY_CHOICES,
        rng=rng,
    )

    trials = []
    for run_index, (run_length, minority_type) in enumerate(
        zip(run_lengths, minority_types), start=1
    ):
        for position_in_run in range(1, run_length + 1):
            trials.append({
                "stimulus_type": dominant_type,
                "is_minority": False,
                "dominant_run_index": run_index,
                "dominant_run_length": run_length,
                "position_in_dominant_run": position_in_run,
            })
        trials.append({
            "stimulus_type": minority_type,
            "is_minority": True,
            "dominant_run_index": run_index,
            "dominant_run_length": run_length,
            "position_in_dominant_run": "",
        })

    validate_main_block(trials, block_type, expected_counts)
    return trials, run_lengths, minority_types


def validate_main_block(trials, block_type, expected_counts):
    if len(trials) != MAIN_TRIAL_COUNT:
        raise AssertionError(f"{block_type}: expected 150 trials, found {len(trials)}")
    counts = Counter(trial["stimulus_type"] for trial in trials)
    if dict(counts) != expected_counts:
        raise AssertionError(f"{block_type}: unexpected counts {dict(counts)}")

    run_lengths = []
    minority_stream = []
    for trial in trials:
        if trial["is_minority"]:
            run_lengths.append(trial["dominant_run_length"])
            minority_stream.append(trial["stimulus_type"])
    if len(run_lengths) != 38 or sum(run_lengths) != 112:
        raise AssertionError(f"{block_type}: invalid dominant run structure")
    if any(length < 1 or length > 4 for length in run_lengths):
        raise AssertionError(f"{block_type}: dominant run outside 1..4")
    if has_run_longer_than(run_lengths, MAX_IDENTICAL_RUN_LENGTH_CHOICES):
        raise AssertionError(f"{block_type}: the same run length appears 3 times in a row")
    if has_run_longer_than(minority_stream, MAX_IDENTICAL_MINORITY_CHOICES):
        raise AssertionError(f"{block_type}: the same minority type appears 4 times in a row")


def balanced_image_sequence(paths, count, rng):
    paths = list(paths)
    if not paths:
        raise ValueError("Cannot create an image sequence from an empty pool")

    output = []
    previous = None
    while len(output) < count:
        cycle = list(paths)
        rng.shuffle(cycle)
        if previous is not None and len(cycle) > 1 and cycle[0] == previous:
            cycle[0], cycle[1] = cycle[1], cycle[0]
        needed = count - len(output)
        output.extend(cycle[:needed])
        previous = output[-1]
    return output


def attach_images(trials, set_info, rng):
    counts = Counter(trial["stimulus_type"] for trial in trials)
    near_sequence = balanced_image_sequence(set_info["near_paths"], counts[NEAR], rng)
    far_sequence = balanced_image_sequence(set_info["far_paths"], counts[FAR], rng)
    near_index = 0
    far_index = 0

    for trial in trials:
        stimulus_type = trial["stimulus_type"]
        if stimulus_type == TARGET:
            image_path = set_info["target_path"]
        elif stimulus_type == NEAR:
            image_path = near_sequence[near_index]
            near_index += 1
        elif stimulus_type == FAR:
            image_path = far_sequence[far_index]
            far_index += 1
        else:
            raise ValueError(f"Unknown stimulus type: {stimulus_type}")

        trial["image_path"] = image_path
        trial["stimulus_pattern"] = pattern_from_path(image_path)
        trial["stimulus_pattern_id"] = pattern_id(trial["stimulus_pattern"])
        trial["target_pattern"] = set_info["target_pattern"]
        trial["target_pattern_id"] = pattern_id(trial["target_pattern"])
        trial["target_set"] = set_info["set_name"]


def annotate_nogo_counts(trials):
    """Record actual presented NoGo count on Target rows, resetting per block."""
    nogo_count = 0
    for trial in trials:
        if trial["stimulus_type"] == TARGET:
            trial["nogo_count_since_last_target"] = nogo_count
            nogo_count = 0
        else:
            trial["nogo_count_since_last_target"] = ""
            nogo_count += 1


def load_counterbalance_schedule(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    required = {
        "counterbalance_cell_id",
        "block_a_set_id",
        "block_a_type",
        "block_b_set_id",
        "block_b_type",
    }
    if not rows:
        raise ValueError("The counterbalance schedule is empty")
    if not required.issubset(rows[0]):
        missing = sorted(required - set(rows[0]))
        raise ValueError(f"Counterbalance schedule is missing columns: {missing}")
    return rows


def select_counterbalance_cell(rows, subject_index):
    text = str(subject_index).strip()
    if text.isdigit():
        numeric_index = int(text)
        position = (
            (numeric_index - 1) % len(rows)
            if numeric_index > 0
            else 0
        )
    else:
        position = sum(ord(character) for character in text) % len(rows)
    return dict(rows[position])


def clone_set(item):
    return dict(
        item,
        near_paths=list(item["near_paths"]),
        far_paths=list(item["far_paths"]),
    )


def select_practice_sets(
    catalog,
    main_set_names,
    main_forbidden_patterns,
    rng,
    attempt_count=MAX_PRACTICE_ATTEMPTS,
):
    eligible = []
    for item in catalog:
        if item["set_name"] in main_set_names:
            continue
        candidate = clone_set(item)
        candidate["near_paths"] = [
            path
            for path in candidate["near_paths"]
            if pattern_from_path(path) not in main_forbidden_patterns
        ]
        candidate["far_paths"] = [
            path
            for path in candidate["far_paths"]
            if pattern_from_path(path) not in main_forbidden_patterns
        ]
        if len(candidate["near_paths"]) >= 5 and len(candidate["far_paths"]) >= 5:
            eligible.append(candidate)

    if len(eligible) < attempt_count:
        raise ValueError(
            f"Need {attempt_count} practice-eligible sets; found {len(eligible)}"
        )

    selected = rng.sample(eligible, attempt_count)
    allocation = {
        "selection_rule": "different_sets_without_replacement",
        "main_pattern_overlap_excluded": True,
        "pool_sizes_by_set": {
            item["set_name"]: {
                "Near": len(item["near_paths"]),
                "Far": len(item["far_paths"]),
            }
            for item in selected
        },
    }
    return selected, allocation


def build_experiment_plan(
    catalog,
    rng,
    main_set_names,
    counterbalance_cell,
    balanced_pool_size,
    practice_attempt_count=MAX_PRACTICE_ATTEMPTS,
):
    catalog_by_name = {item["set_name"]: item for item in catalog}
    missing_main_sets = [
        set_name for set_name in main_set_names if set_name not in catalog_by_name
    ]
    if missing_main_sets:
        raise ValueError(f"Unknown fixed main sets: {missing_main_sets}")

    main_sets = [clone_set(catalog_by_name[name]) for name in main_set_names]
    all_catalog_targets = {item["target_pattern"] for item in catalog}
    main_pool_allocation = allocate_balanced_candidate_pools(
        main_sets,
        balanced_pool_size,
        forbidden_patterns=all_catalog_targets,
    )
    main_by_name = {item["set_name"]: item for item in main_sets}

    block_a_set_name = counterbalance_cell["block_a_set_id"]
    block_b_set_name = counterbalance_cell["block_b_set_id"]
    if block_a_set_name not in main_by_name or block_b_set_name not in main_by_name:
        raise ValueError("Counterbalance cell references a set outside the main triplet")
    if block_a_set_name == block_b_set_name:
        raise ValueError("Block A and Block B must use different target sets")
    block_a_type = counterbalance_cell["block_a_type"]
    block_b_type = counterbalance_cell["block_b_type"]
    if {block_a_type, block_b_type} != {HEAVY_GO, LOW_GO}:
        raise ValueError("Every counterbalance cell must contain one Heavy-go and one Low-go")

    block_a_set = main_by_name[block_a_set_name]
    block_b_set = main_by_name[block_b_set_name]
    main_forbidden_patterns = set(all_catalog_targets)
    for item in (block_a_set, block_b_set):
        main_forbidden_patterns.update(
            pattern_from_path(path)
            for path in item["near_paths"] + item["far_paths"]
        )
    practice_sets, practice_pool_allocation = select_practice_sets(
        catalog,
        set(main_set_names),
        main_forbidden_patterns,
        rng,
        attempt_count=practice_attempt_count,
    )

    block_a_trials, block_a_runs, block_a_minorities = make_main_block_trials(
        block_a_type, rng
    )
    block_b_trials, block_b_runs, block_b_minorities = make_main_block_trials(
        block_b_type, rng
    )

    practice_blocks = []
    practice_global_index = 1
    for attempt, practice_set in enumerate(practice_sets, start=1):
        trials, counts = make_practice_trials(rng)
        attach_images(trials, practice_set, rng)
        annotate_nogo_counts(trials)
        for trial_index, trial in enumerate(trials, start=1):
            trial["practice_attempt"] = attempt
            trial["block_trial_index"] = trial_index
            trial["global_trial_index"] = practice_global_index
            trial["phase"] = PRACTICE
            trial["block_type"] = PRACTICE
            trial["block_index"] = 0
            trial["counterbalance_cell_id"] = counterbalance_cell[
                "counterbalance_cell_id"
            ]
            practice_global_index += 1
        practice_blocks.append(
            {
                "block_index": 0,
                "phase": PRACTICE,
                "block_type": PRACTICE,
                "practice_attempt": attempt,
                "set_info": practice_set,
                "trials": trials,
                "counts": counts,
                "run_lengths": [],
                "minority_stream": [],
            }
        )

    attach_images(block_a_trials, block_a_set, rng)
    attach_images(block_b_trials, block_b_set, rng)
    annotate_nogo_counts(block_a_trials)
    annotate_nogo_counts(block_b_trials)

    main_blocks = [
        {
            "block_index": 1,
            "phase": "Block A",
            "block_type": block_a_type,
            "set_info": block_a_set,
            "trials": block_a_trials,
            "counts": dict(Counter(t["stimulus_type"] for t in block_a_trials)),
            "run_lengths": block_a_runs,
            "minority_stream": block_a_minorities,
        },
        {
            "block_index": 2,
            "phase": "Block B",
            "block_type": block_b_type,
            "set_info": block_b_set,
            "trials": block_b_trials,
            "counts": dict(Counter(t["stimulus_type"] for t in block_b_trials)),
            "run_lengths": block_b_runs,
            "minority_stream": block_b_minorities,
        },
    ]

    global_index = 1
    for block in main_blocks:
        for trial_index, trial in enumerate(block["trials"], start=1):
            trial["practice_attempt"] = ""
            trial["block_trial_index"] = trial_index
            trial["global_trial_index"] = global_index
            trial["phase"] = block["phase"]
            trial["block_type"] = block["block_type"]
            trial["block_index"] = block["block_index"]
            trial["counterbalance_cell_id"] = counterbalance_cell[
                "counterbalance_cell_id"
            ]
            global_index += 1

    selection = {
        "triplet_rank": 1,
        "main_set_triplet": list(main_set_names),
        "counterbalance_cell_id": counterbalance_cell["counterbalance_cell_id"],
        "practice_sets": [item["set_name"] for item in practice_sets],
        "practice_targets": [item["target_pattern"] for item in practice_sets],
        "practice_set": "|".join(item["set_name"] for item in practice_sets),
        "block_a_set": block_a_set["set_name"],
        "block_a_target": block_a_set["target_pattern"],
        "block_a_type": block_a_type,
        "block_b_set": block_b_set["set_name"],
        "block_b_target": block_b_set["target_pattern"],
        "block_b_type": block_b_type,
        "candidate_pool_allocation": main_pool_allocation,
        "practice_pool_allocation": practice_pool_allocation,
    }
    return practice_blocks, main_blocks, selection


def write_planned_schedule(path, blocks, project_dir):
    fields = [
        "global_trial_index", "block_index", "phase", "block_type",
        "practice_attempt", "counterbalance_cell_id", "block_trial_index",
        "target_set", "target_pattern_id", "stimulus_pattern_id",
        "target_pattern", "stimulus_pattern",
        "stimulus_type", "is_minority", "dominant_run_index",
        "dominant_run_length", "position_in_dominant_run", "image_path",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for block in blocks:
            for trial in block["trials"]:
                row = {field: trial.get(field, "") for field in fields}
                row["image_path"] = str(
                    Path(row["image_path"]).relative_to(project_dir)
                )
                for field, value in tuple(row.items()):
                    if isinstance(value, bool):
                        row[field] = 1 if value else 0
                writer.writerow(row)
