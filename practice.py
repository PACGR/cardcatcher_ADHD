# -*- coding: utf-8 -*-
"""Standalone, main-paced practice acquisition for CARD CATCHER."""

from datetime import datetime
from pathlib import Path
import ctypes
import json
import random
import secrets


if hasattr(ctypes, "windll"):
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass


import psychopy
from psychopy import core, data, event, gui, visual
from psychopy.hardware import keyboard

from key_events import KEY_EVENT_FIELDS, PhysicalKeyTracker
from display_utils import (
    get_primary_display_size,
    load_cardgame_display_layout,
    measure_refresh_hz,
    serializable_display_info,
)
from runtime import (
    AsyncTrialWriter,
    ExperimentAbort,
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
PRACTICE_RUN_COUNT = 2

SCREEN_SIZE = (2880, 1800)

PROJECT_DIR = Path(__file__).resolve().parent
SETS_DIR = PROJECT_DIR / "assets" / "sets"
BACKGROUND_PATH = (
    PROJECT_DIR
    / "assets"
    / "backgrounds"
    / "card-catcher-background-2880x1800.png"
)
LAYOUT_PATH = (
    PROJECT_DIR
    / "assets"
    / "backgrounds"
    / "card-catcher-background-2880x1800.layout.json"
)
COUNTERBALANCE_PATH = (
    PROJECT_DIR / "assets" / "codebooks" / "counterbalance_schedule.tsv"
)


def save_practice_config(
    path,
    subject_info,
    session_seed,
    selection,
    practice_blocks,
    practice_results=None,
    session_timestamps=None,
    task_status="started",
    display_info=None,
):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "task": "standalone_practice",
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
                "practice_run_count": len(practice_blocks),
                "practice_blocks": [
                    {
                        "practice_attempt": block["practice_attempt"],
                        "target_set": block["set_info"]["set_name"],
                        "target_pattern": block["set_info"]["target_pattern"],
                        "target_pattern_id": pattern_id(
                            block["set_info"]["target_pattern"]
                        ),
                        "counts": block["counts"],
                    }
                    for block in practice_blocks
                ],
                "practice_results": practice_results or [],
                "session_timestamps": session_timestamps or {},
                "display": display_info or {},
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def select_standalone_practice_blocks(
    practice_blocks,
    run_count=PRACTICE_RUN_COUNT,
):
    selected = list(practice_blocks[:run_count])
    if len(selected) != run_count:
        raise RuntimeError(
            f"Practice requires {run_count} distinct sets; found {len(selected)}"
        )
    set_names = [block["set_info"]["set_name"] for block in selected]
    if len(set(set_names)) != len(set_names):
        raise RuntimeError("Practice attempts must use distinct target sets")
    return selected


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
        height=58 * ui_scale,
        color="#17342f",
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
        title="CARD CATCHER - PRACTICE",
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

    # Fail before participant files are created if the fixed display assets or
    # layout metadata are missing/corrupt.
    load_cardgame_display_layout(
        SCREEN_SIZE,
        BACKGROUND_PATH,
        LAYOUT_PATH,
    )

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
        practice_attempt_count=PRACTICE_RUN_COUNT,
    )
    practice_blocks = select_standalone_practice_blocks(practice_blocks)

    raw_dir = (
        PROJECT_DIR
        / "data"
        / f"{subject_info['SubType']}-{subject_info['SubIdx']}"
        / "raw"
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    session_name = (
        f"{subject_info['SubType']}-{subject_info['SubIdx']}_"
        f"{subject_info['SubSes']}_{subject_info['date']}_p01-p02"
    )
    schedule_path = raw_dir / f"{session_name}_practice_schedule.tsv"
    data_path = raw_dir / f"{session_name}_practice_trials.tsv"
    key_events_path = raw_dir / f"{session_name}_practice_key_events.tsv"
    summary_path = raw_dir / f"{session_name}_practice_summary.tsv"
    config_path = raw_dir / f"{session_name}_practice_config.json"

    write_planned_schedule(
        schedule_path,
        practice_blocks,
        PROJECT_DIR,
    )
    session_timestamps = {
        "program_started_at": datetime.now().astimezone().isoformat(),
        "program_ended_at": "",
        "session_elapsed_ms": "",
    }
    practice_results = []
    task_status = "started"
    display_info = {}
    save_practice_config(
        config_path,
        subject_info,
        session_seed,
        selection,
        practice_blocks,
        session_timestamps=session_timestamps,
        task_status=task_status,
        display_info=display_info,
    )

    trial_writer = AsyncTrialWriter(data_path, RUNTIME_FIELDS)
    key_event_writer = AsyncTrialWriter(key_events_path, KEY_EVENT_FIELDS)
    summary_writer = AsyncTrialWriter(
        summary_path,
        PRACTICE_SUMMARY_FIELDS,
    )
    win = None
    session_clock = None
    key_event_recorder = None

    try:
        win = visual.Window(
            size=get_primary_display_size(SCREEN_SIZE),
            fullscr=True,
            allowGUI=False,
            units="pix",
            color="#f5f0e5",
            winType="pyglet",
        )
        event.Mouse(visible=False)
        actual_screen_size = tuple(int(value) for value in win.size)
        display_layout = load_cardgame_display_layout(
            actual_screen_size,
            BACKGROUND_PATH,
            LAYOUT_PATH,
        )
        display_scale = display_layout["display_scale"]
        target_position = display_layout["target_position"]
        target_size = display_layout["target_size"]
        stimulus_position = display_layout["stimulus_position"]
        stimulus_size = display_layout["stimulus_size"]
        display_info = serializable_display_info(display_layout)

        background_stim = visual.ImageStim(
            win,
            image=str(BACKGROUND_PATH),
            pos=(0, 0),
            size=display_layout["background_size"],
            units="pix",
            interpolate=True,
        )
        kb = keyboard.Keyboard()
        session_clock = core.Clock()
        key_event_recorder = PhysicalKeyTracker(
            session_clock.getLastResetTime(),
            key_event_writer.submit,
        )

        refresh_hz, refresh_measurement_source = measure_refresh_hz(win)
        display_info.update({
            "refresh_hz": round(refresh_hz, 6),
            "refresh_measurement_source": refresh_measurement_source,
            "psychopy_version": psychopy.__version__,
            "keyboard_backend": str(kb.getBackend()),
        })

        for practice_block in practice_blocks:
            runtime_rows = []

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

            temporary_reference = visual.ImageStim(
                win,
                image=str(practice_block["set_info"]["target_path"]),
                pos=target_position,
                size=target_size,
                units="pix",
                interpolate=True,
            )
            attempt_number = practice_block["practice_attempt"]
            show_loading(
                win,
                background_stim,
                temporary_reference,
                f"연습 {attempt_number}",
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
                f"연습 {attempt_number}을 시작합니다",
                "왼쪽 기준 카드와 완전히 같은 카드가 나올 때만 "
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
                "practice_attempt": attempt_number,
                "practice_set_id": practice_block["set_info"]["set_name"],
                "target_pattern_id": pattern_id(
                    practice_block["set_info"]["target_pattern"]
                ),
                **summary,
                # Main acquisition is a separate operator-launched program.
                "advanced_to_main": False,
                "forced_proceed_after_max_attempts": False,
            }
            practice_results.append(practice_result)
            summary_writer.submit(practice_result)
            summary_writer.checkpoint()

            center_stimuli.clear()
            del reference_stim
            del temporary_reference

        task_status = "completed"

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
            practice_blocks,
            practice_results=practice_results,
            session_timestamps=session_timestamps,
            task_status=task_status,
            display_info=display_info,
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
