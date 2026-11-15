# -*- coding: utf-8 -*-
"""Standalone, main-paced practice for the minimal-black task variant."""

from datetime import datetime
from pathlib import Path
import ctypes
import json
import random
import secrets
import sys


VARIANT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = VARIANT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.append(str(PROJECT_DIR))


if hasattr(ctypes, "windll"):
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass


import psychopy
from psychopy import core, data, event, gui, visual
from psychopy.hardware import keyboard

from key_events import KEY_EVENT_FIELDS, PhysicalKeyTracker
from display_utils import get_primary_display_size, measure_refresh_hz
from runtime import (
    AsyncTrialWriter,
    ExperimentAbort,
    PatternGridStimulus,
    PRACTICE_SUMMARY_FIELDS,
    RUNTIME_FIELDS,
    make_runtime_row,
    prepare_block_stimuli,
    run_block,
    show_gate,
    show_loading,
    summarize_practice,
)
from schedule import (
    build_experiment_plan,
    load_counterbalance_schedule,
    load_set_catalog,
    pattern_id,
    select_counterbalance_cell,
    write_planned_schedule,
)
from main import TIMING
from session_utils import normalize_session_inputs


TARGET_SELECTION_MODE = "fixed_rank1_triplet_counterbalanced"
MAIN_SET_NAMES = ("set05", "set10", "set12")
BALANCED_POOL_SIZE = None
SCREEN_SIZE = (2880, 1800)

SETS_DIR = PROJECT_DIR / "assets" / "sets"
COUNTERBALANCE_PATH = (
    PROJECT_DIR / "assets" / "codebooks" / "counterbalance_schedule.tsv"
)


def save_practice_config(
    path,
    subject_info,
    session_seed,
    selection,
    practice_block,
    practice_result=None,
    session_timestamps=None,
    task_status="started",
    runtime_info=None,
):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "task": "standalone_practice",
                "task_variant": "minimal_black",
                "task_status": task_status,
                "subject": subject_info,
                "session_seed": session_seed,
                "target_selection_mode": TARGET_SELECTION_MODE,
                "main_set_names_used_for_stimulus_separation": list(
                    MAIN_SET_NAMES
                ),
                "selection": selection,
                "timing": {
                    "stimulus_seconds": TIMING.stimulus_seconds,
                    "trial_seconds": TIMING.trial_seconds,
                    "premature_seconds": TIMING.premature_seconds,
                    "trial_feedback_seconds": 0.0,
                    "matches_main_task": True,
                },
                "practice_block": {
                    "practice_attempt": practice_block["practice_attempt"],
                    "target_set": practice_block["set_info"]["set_name"],
                    "target_pattern": practice_block["set_info"]["target_pattern"],
                    "target_pattern_id": pattern_id(
                        practice_block["set_info"]["target_pattern"]
                    ),
                    "counts": practice_block["counts"],
                },
                "practice_result": practice_result or {},
                "session_timestamps": session_timestamps or {},
                "runtime": runtime_info or {},
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def show_practice_complete_until_escape(
    win,
    kb,
    background_stim,
    ui_scale=1.0,
):
    message = visual.TextStim(
        win,
        text="연습이 끝났습니다",
        font="Malgun Gothic",
        height=52 * ui_scale,
        color="#f2f2f2",
        pos=(0, 0),
        bold=True,
        units="pix",
    )
    background_stim.draw()
    message.draw()
    win.flip()

    kb.clearEvents()
    while True:
        keys = kb.getKeys(
            keyList=["escape"],
            waitRelease=False,
            clear=True,
        )
        if keys:
            raise ExperimentAbort()
        core.wait(0.01)


def main():
    subject_info = {
        "SubType": "CLD",
        "SubIdx": "001",
        "SubSes": "001",
        "Seed": "",
    }
    dialog = gui.DlgFromDict(
        dictionary=subject_info,
        title="CARD CATCHER — MINIMAL BLACK PRACTICE",
    )
    if not dialog.OK:
        core.quit()

    try:
        subject_info, entered_seed = normalize_session_inputs(subject_info)
    except ValueError as exc:
        error_dialog = gui.Dlg(title="입력 오류")
        error_dialog.addText(str(exc))
        error_dialog.show()
        core.quit()

    subject_info["date"] = data.getDateStr()
    session_seed = (
        entered_seed if entered_seed is not None else secrets.randbits(32)
    )
    rng = random.Random(session_seed)

    catalog = load_set_catalog(SETS_DIR)
    counterbalance_rows = load_counterbalance_schedule(COUNTERBALANCE_PATH)
    counterbalance_cell = select_counterbalance_cell(
        counterbalance_rows,
        subject_info["SubIdx"],
    )
    practice_blocks, _main_blocks, selection = build_experiment_plan(
        catalog,
        rng,
        main_set_names=MAIN_SET_NAMES,
        counterbalance_cell=counterbalance_cell,
        balanced_pool_size=BALANCED_POOL_SIZE,
    )
    practice_block = practice_blocks[0]

    raw_dir = (
        PROJECT_DIR
        / "data"
        / f"{subject_info['SubType']}-{subject_info['SubIdx']}"
        / "raw"
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    session_name = (
        f"{subject_info['SubType']}-{subject_info['SubIdx']}_"
        f"{subject_info['SubSes']}_{subject_info['date']}_minimalblack_p01"
    )
    schedule_path = raw_dir / f"{session_name}_practice_schedule.tsv"
    data_path = raw_dir / f"{session_name}_practice_trials.tsv"
    key_events_path = raw_dir / f"{session_name}_practice_key_events.tsv"
    summary_path = raw_dir / f"{session_name}_practice_summary.tsv"
    config_path = raw_dir / f"{session_name}_practice_config.json"

    write_planned_schedule(
        schedule_path,
        [practice_block],
        PROJECT_DIR,
    )
    session_timestamps = {
        "program_started_at": datetime.now().astimezone().isoformat(),
        "program_ended_at": "",
        "session_elapsed_ms": "",
    }
    practice_result = {}
    task_status = "started"
    save_practice_config(
        config_path,
        subject_info,
        session_seed,
        selection,
        practice_block,
        session_timestamps=session_timestamps,
        task_status=task_status,
    )

    trial_writer = AsyncTrialWriter(data_path, RUNTIME_FIELDS)
    key_event_writer = AsyncTrialWriter(key_events_path, KEY_EVENT_FIELDS)
    summary_writer = AsyncTrialWriter(
        summary_path,
        PRACTICE_SUMMARY_FIELDS,
    )
    runtime_rows = []
    win = None
    session_clock = None
    key_event_recorder = None
    runtime_info = {}

    try:
        win = visual.Window(
            size=get_primary_display_size(SCREEN_SIZE),
            fullscr=True,
            allowGUI=False,
            units="pix",
            color="#000000",
            winType="pyglet",
        )
        event.Mouse(visible=False)
        actual_screen_size = tuple(int(value) for value in win.size)
        display_scale = min(
            actual_screen_size[0] / SCREEN_SIZE[0],
            actual_screen_size[1] / SCREEN_SIZE[1],
        )
        target_position = (-0.27 * actual_screen_size[0], 0)
        target_size = (300 * display_scale, 300 * display_scale)
        stimulus_position = (0, 0)
        stimulus_size = (360 * display_scale, 360 * display_scale)

        background_stim = visual.Rect(
            win,
            pos=(0, 0),
            width=actual_screen_size[0],
            height=actual_screen_size[1],
            fillColor="#000000",
            lineColor="#000000",
            units="pix",
        )
        fixation_stim = visual.TextStim(
            win,
            text="+",
            pos=(0, 0),
            height=48 * display_scale,
            color="#f2f2f2",
            units="pix",
        )
        kb = keyboard.Keyboard()
        session_clock = core.Clock()
        key_event_recorder = PhysicalKeyTracker(
            session_clock.getLastResetTime(),
            key_event_writer.submit,
        )

        refresh_hz, _refresh_measurement_source = measure_refresh_hz(win)
        runtime_info = {
            "psychopy_version": psychopy.__version__,
            "keyboard_backend": str(kb.getBackend()),
        }

        def save_completed_trial(
            trial,
            runtime,
            stimulus_frames,
            trial_frames,
        ):
            runtime_rows.append(runtime)
            trial_writer.submit(
                make_runtime_row(
                    subject_info,
                    session_seed,
                    selection,
                    trial,
                    runtime,
                    refresh_hz,
                    stimulus_frames,
                    trial_frames,
                    TIMING,
                    TARGET_SELECTION_MODE,
                    PROJECT_DIR,
                )
            )

        temporary_reference = PatternGridStimulus(
            win,
            pattern=practice_block["set_info"]["target_pattern"],
            pos=target_position,
            size=target_size,
        )
        show_loading(
            win,
            background_stim,
            temporary_reference,
            "연습",
            ui_scale=display_scale,
        )
        center_stimuli, reference_stim = prepare_block_stimuli(
            win,
            practice_block,
            stimulus_position,
            stimulus_size,
            target_position,
            target_size,
        )
        show_gate(
            win,
            kb,
            background_stim,
            reference_stim,
            "연습을 시작합니다",
            "왼쪽 기준 패턴과 완전히 같은 패턴이 나올 때만 "
            "SPACE를 누르세요.\n준비가 되면 SPACE를 누르세요.",
            ui_scale=display_scale,
            key_event_recorder=key_event_recorder,
        )
        run_block(
            win,
            kb,
            session_clock,
            background_stim,
            reference_stim,
            center_stimuli,
            practice_block,
            refresh_hz,
            TIMING,
            save_completed_trial,
            fixation_stim=fixation_stim,
            key_event_recorder=key_event_recorder,
        )
        trial_writer.checkpoint()
        key_event_writer.checkpoint()

        summary = summarize_practice(practice_block, runtime_rows)
        practice_result = {
            "subject": subject_info["SubIdx"],
            "session": subject_info["SubSes"],
            "subject_type": subject_info["SubType"],
            "date": subject_info["date"],
            "session_seed": session_seed,
            "practice_attempt": practice_block["practice_attempt"],
            "practice_set_id": practice_block["set_info"]["set_name"],
            "target_pattern_id": pattern_id(
                practice_block["set_info"]["target_pattern"]
            ),
            **summary,
            "advanced_to_main": False,
            "forced_proceed_after_max_attempts": False,
        }
        summary_writer.submit(practice_result)
        summary_writer.checkpoint()
        task_status = "completed"

        center_stimuli.clear()
        del reference_stim
        del temporary_reference

        show_practice_complete_until_escape(
            win,
            kb,
            background_stim,
            ui_scale=display_scale,
        )

    except ExperimentAbort:
        if task_status != "completed":
            task_status = "aborted"
    finally:
        session_timestamps["program_ended_at"] = (
            datetime.now().astimezone().isoformat()
        )
        if session_clock is not None:
            session_timestamps["session_elapsed_ms"] = round(
                session_clock.getTime() * 1000,
                3,
            )
        save_practice_config(
            config_path,
            subject_info,
            session_seed,
            selection,
            practice_block,
            practice_result=practice_result,
            session_timestamps=session_timestamps,
            task_status=task_status,
            runtime_info=runtime_info,
        )
        if win is not None:
            win.close()
        trial_writer.close()
        if key_event_recorder is not None:
            key_event_recorder.flush()
        key_event_writer.close()
        summary_writer.close()

    core.quit()


if __name__ == "__main__":
    main()
