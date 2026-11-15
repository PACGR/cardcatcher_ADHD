# -*- coding: utf-8 -*-

from pathlib import Path
import ctypes
import json
import random
import secrets
from datetime import datetime


# Let PsychoPy use the monitor's physical pixels even when Windows display
# scaling is above 100%. If Windows has already chosen a DPI mode, the
# resolution-aware layout below remains the fallback.
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
    RUNTIME_FIELDS,
    Timing,
    make_runtime_row,
    prepare_block_stimuli,
    run_block,
    show_gate,
    show_loading,
)
from schedule import (
    build_experiment_plan,
    load_set_catalog,
    load_counterbalance_schedule,
    select_counterbalance_cell,
    write_planned_schedule,
)
from session_utils import normalize_session_inputs


# ============================================================
# Experiment settings: edit these lines when needed
# ============================================================

TARGET_SELECTION_MODE = "fixed_rank1_triplet_counterbalanced"
MAIN_SET_NAMES = ("set05", "set10", "set12")
BALANCED_POOL_SIZE = None

SCREEN_SIZE = (2880, 1800)
TIMING = Timing(
    stimulus_seconds=0.45,
    trial_seconds=0.9,
    premature_seconds=0.1,
)

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


def save_session_config(
    path,
    subject_info,
    session_seed,
    selection,
    main_blocks,
    session_timestamps=None,
    display_info=None,
):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "subject": subject_info,
                "session_seed": session_seed,
                "target_selection_mode": TARGET_SELECTION_MODE,
                "main_set_names": list(MAIN_SET_NAMES),
                "balanced_pool_size_setting": BALANCED_POOL_SIZE,
                "counterbalance_schedule": str(
                    COUNTERBALANCE_PATH.relative_to(PROJECT_DIR)
                ),
                "selection": selection,
                "timing": {
                    "stimulus_seconds": TIMING.stimulus_seconds,
                    "trial_seconds": TIMING.trial_seconds,
                    "premature_seconds": TIMING.premature_seconds,
                },
                "blocks": [
                    {
                        "phase": block["phase"],
                        "block_type": block["block_type"],
                        "target_set": block["set_info"]["set_name"],
                        "target_pattern": block["set_info"]["target_pattern"],
                        "counts": block["counts"],
                        "run_lengths": block["run_lengths"],
                        "minority_stream": block["minority_stream"],
                    }
                    for block in main_blocks
                ],
                "session_timestamps": session_timestamps or {},
                "display": display_info or {},
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def main():
    subject_info = {
        "SubType": "CLD",
        "SubIdx": "001",
        "SubSes": "001",
        "Seed": "",
    }
    dialog = gui.DlgFromDict(dictionary=subject_info, title="CARD CATCHER")
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
    _practice_blocks, main_blocks, selection = build_experiment_plan(
        catalog,
        rng,
        main_set_names=MAIN_SET_NAMES,
        counterbalance_cell=counterbalance_cell,
        balanced_pool_size=BALANCED_POOL_SIZE,
    )

    raw_dir = (
        PROJECT_DIR
        / "data"
        / f"{subject_info['SubType']}-{subject_info['SubIdx']}"
        / "raw"
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    session_name = (
        f"{subject_info['SubType']}-{subject_info['SubIdx']}_"
        f"{subject_info['SubSes']}_{subject_info['date']}"
    )
    schedule_path = raw_dir / f"{session_name}_schedule.tsv"
    data_path = raw_dir / f"{session_name}_trials.tsv"
    key_events_path = raw_dir / f"{session_name}_key_events.tsv"
    config_path = raw_dir / f"{session_name}_config.json"

    write_planned_schedule(schedule_path, main_blocks, PROJECT_DIR)
    session_timestamps = {
        "program_started_at": datetime.now().astimezone().isoformat(),
        "program_ended_at": "",
        "session_elapsed_ms": "",
    }
    display_info = {}
    save_session_config(
        config_path,
        subject_info,
        session_seed,
        selection,
        main_blocks,
        session_timestamps=session_timestamps,
        display_info=display_info,
    )
    trial_writer = AsyncTrialWriter(data_path, RUNTIME_FIELDS)
    key_event_writer = AsyncTrialWriter(key_events_path, KEY_EVENT_FIELDS)

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

        def save_completed_trial(trial, runtime, stimulus_frames, trial_frames):
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

        save_session_config(
            config_path,
            subject_info,
            session_seed,
            selection,
            main_blocks,
            session_timestamps=session_timestamps,
            display_info=display_info,
        )

        gate_specs = [
            (
                "스페이스바를 눌러 블록A를 시작하시오",
                "",
                "",
            ),
            (
                "휴식 시간입니다.\n"
                "준비가 되면 스페이스바를 눌러 블록 B를 시작하세요.",
                "",
                "",
            ),
        ]

        for block, (gate_title, gate_body, gate_key_text) in zip(
            main_blocks,
            gate_specs,
        ):
            temporary_reference = visual.ImageStim(
                win,
                image=str(block["set_info"]["target_path"]),
                pos=target_position,
                size=target_size,
                units="pix",
                interpolate=True,
            )
            show_loading(
                win,
                background_stim,
                temporary_reference,
                block["phase"],
                ui_scale=display_scale,
            )
            center_stimuli, reference_stim = prepare_block_stimuli(
                win,
                block,
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
                gate_title,
                gate_body,
                ui_scale=display_scale,
                key_text=gate_key_text,
                key_event_recorder=key_event_recorder,
            )
            run_block(
                win,
                kb,
                session_clock,
                background_stim,
                reference_stim,
                center_stimuli,
                block,
                refresh_hz,
                TIMING,
                save_completed_trial,
                key_event_recorder=key_event_recorder,
            )
            trial_writer.checkpoint()
            key_event_writer.checkpoint()

            center_stimuli.clear()
            del reference_stim
            del temporary_reference

        completion_text = visual.TextStim(
            win,
            text="모든 과제가 끝났습니다.\n참여해 주셔서 감사합니다.",
            font="Malgun Gothic",
            height=48 * display_scale,
            color="#17342f",
            pos=(0, 0),
            units="pix",
        )
        background_stim.draw()
        completion_text.draw()
        win.flip()
        core.wait(3.0)

    except ExperimentAbort:
        pass
    finally:
        session_timestamps["program_ended_at"] = datetime.now().astimezone().isoformat()
        if session_clock is not None:
            session_timestamps["session_elapsed_ms"] = round(
                session_clock.getTime() * 1000,
                3,
            )
        save_session_config(
            config_path,
            subject_info,
            session_seed,
            selection,
            main_blocks,
            session_timestamps=session_timestamps,
            display_info=display_info,
        )
        if win is not None:
            win.close()
        trial_writer.close()
        if key_event_recorder is not None:
            key_event_recorder.flush()
        key_event_writer.close()

    core.quit()


if __name__ == "__main__":
    main()
