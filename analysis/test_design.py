# -*- coding: utf-8 -*-

from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import random
import unittest

from schedule import (
    FAR,
    HEAVY_GO,
    LOW_GO,
    NEAR,
    TARGET,
    ALL_PATTERNS,
    build_experiment_plan,
    load_counterbalance_schedule,
    load_set_catalog,
    pattern_id,
    select_counterbalance_cell,
    write_planned_schedule,
)


PROJECT_DIR = Path(__file__).resolve().parent.parent
MAIN_SET_NAMES = ("set05", "set10", "set12")


class DesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_set_catalog(PROJECT_DIR / "assets" / "sets")
        cls.cells = load_counterbalance_schedule(
            PROJECT_DIR / "assets" / "codebooks" / "counterbalance_schedule.tsv"
        )

    def test_pattern_ids_are_complete_and_stable(self):
        self.assertEqual(len(ALL_PATTERNS), 84)
        self.assertEqual(len({pattern_id(pattern) for pattern in ALL_PATTERNS}), 84)
        self.assertEqual(pattern_id("000000111"), 1)
        self.assertEqual(pattern_id("111000000"), 84)

    def test_six_cells_balance_set_context_and_order(self):
        self.assertEqual(len(self.cells), 6)
        context_counts = Counter()
        position_counts = Counter()
        block_type_counts = Counter()

        for cell in self.cells:
            self.assertEqual(
                cell["first_block_type"],
                cell["block_a_type"],
            )
            if cell["block_a_type"] == HEAVY_GO:
                self.assertEqual(cell["heavy_set_id"], cell["block_a_set_id"])
                self.assertEqual(cell["low_set_id"], cell["block_b_set_id"])
            else:
                self.assertEqual(cell["low_set_id"], cell["block_a_set_id"])
                self.assertEqual(cell["heavy_set_id"], cell["block_b_set_id"])
            for phase in ("a", "b"):
                set_name = cell[f"block_{phase}_set_id"]
                block_type = cell[f"block_{phase}_type"]
                context_counts[(set_name, block_type)] += 1
                position_counts[(set_name, phase.upper())] += 1
                block_type_counts[(phase.upper(), block_type)] += 1

        for set_name in MAIN_SET_NAMES:
            self.assertEqual(context_counts[(set_name, HEAVY_GO)], 2)
            self.assertEqual(context_counts[(set_name, LOW_GO)], 2)
            self.assertEqual(position_counts[(set_name, "A")], 2)
            self.assertEqual(position_counts[(set_name, "B")], 2)
        self.assertEqual(block_type_counts[("A", HEAVY_GO)], 3)
        self.assertEqual(block_type_counts[("A", LOW_GO)], 3)

    def test_numeric_counterbalance_assignment_cycles_and_handles_pilot_zero(self):
        self.assertEqual(
            select_counterbalance_cell(
                self.cells,
                "000",
            )["counterbalance_cell_id"],
            "1",
        )
        observed = [
            select_counterbalance_cell(
                self.cells,
                f"{subject_index:03d}",
            )["counterbalance_cell_id"]
            for subject_index in range(1, 13)
        ]
        self.assertEqual(
            observed,
            ["1", "2", "3", "4", "5", "6"] * 2,
        )

    def test_every_cell_builds_valid_practice_and_main_schedules(self):
        for index, cell in enumerate(self.cells, start=1):
            practice, main, selection = build_experiment_plan(
                self.catalog,
                random.Random(20260728 + index),
                MAIN_SET_NAMES,
                cell,
                None,
            )
            self.assertEqual(len(practice), 3)
            self.assertEqual(len({block["set_info"]["set_name"] for block in practice}), 3)
            self.assertTrue(
                all(
                    block["set_info"]["set_name"] not in MAIN_SET_NAMES
                    for block in practice
                )
            )
            for block in practice:
                self.assertEqual(len(block["trials"]), 15)
                self.assertEqual(
                    Counter(trial["stimulus_type"] for trial in block["trials"]),
                    Counter({TARGET: 5, NEAR: 5, FAR: 5}),
                )

            self.assertEqual(len(main), 2)
            self.assertEqual({block["block_type"] for block in main}, {HEAVY_GO, LOW_GO})
            self.assertTrue(all(len(block["trials"]) == 150 for block in main))
            self.assertEqual(
                selection["counterbalance_cell_id"],
                cell["counterbalance_cell_id"],
            )

            practice_patterns = {
                trial["stimulus_pattern"]
                for block in practice
                for trial in block["trials"]
            }
            main_patterns = {
                trial["stimulus_pattern"]
                for block in main
                for trial in block["trials"]
            }
            self.assertFalse(practice_patterns & main_patterns)

    def test_stimulus_manifest_covers_source_catalog(self):
        manifest_path = (
            PROJECT_DIR / "assets" / "codebooks" / "stimulus_manifest.tsv"
        )
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(rows), 746)
        self.assertEqual(len({row["stimulus_id"] for row in rows}), 746)
        self.assertTrue(
            all(1 <= int(row["pattern_id"]) <= 84 for row in rows)
        )
        self.assertTrue(
            all(
                (PROJECT_DIR / row["image_path"]).exists()
                for row in rows
            )
        )

    def test_planned_files_use_ids_and_numeric_booleans(self):
        practice, main, _ = build_experiment_plan(
            self.catalog,
            random.Random(20260728),
            MAIN_SET_NAMES,
            self.cells[0],
            None,
        )
        with TemporaryDirectory() as temporary:
            main_path = Path(temporary) / "main.tsv"
            practice_path = Path(temporary) / "practice.tsv"
            write_planned_schedule(main_path, main, PROJECT_DIR)
            write_planned_schedule(practice_path, practice, PROJECT_DIR)
            with main_path.open("r", encoding="utf-8", newline="") as handle:
                main_rows = list(csv.DictReader(handle, delimiter="\t"))
            with practice_path.open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                practice_rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(main_rows), 300)
        self.assertEqual(len(practice_rows), 45)
        self.assertEqual({row["is_minority"] for row in main_rows}, {"0", "1"})
        self.assertTrue(
            all(row["target_pattern_id"].isdigit() for row in main_rows)
        )
        self.assertTrue(
            all(row["stimulus_pattern_id"].isdigit() for row in practice_rows)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
