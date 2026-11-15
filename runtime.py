# -*- coding: utf-8 -*-

from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
import csv
import os
import queue
import threading

from psychopy import core, visual

from schedule import TARGET


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

PRACTICE_SUMMARY_FIELDS = [
    "subject", "session", "subject_type", "date", "session_seed",
    "practice_attempt", "practice_set_id", "target_pattern_id",
    "target_correct", "target_total", "nogo_correct", "nogo_total",
    "overall_correct", "overall_total", "target_passed", "nogo_passed",
    "overall_passed", "practice_passed", "advanced_to_main",
    "forced_proceed_after_max_attempts",
]


@dataclass(frozen=True)
class Timing:
    stimulus_seconds: float
    trial_seconds: float
    premature_seconds: float


class ExperimentAbort(Exception):
    pass


class AsyncTrialWriter:
    """Append trial rows off the visual-timing thread and checkpoint per block."""

    def __init__(self, path, fieldnames):
        self.path = Path(path)
        self.fieldnames = fieldnames
        self.items = queue.Queue()
        self.ready = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, name="trial-writer")
        self.thread.start()
        self.ready.wait()
        self._raise_if_error()

    def _run(self):
        try:
            with self.path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=self.fieldnames, delimiter="\t"
                )
                writer.writeheader()
                handle.flush()
                self.ready.set()

                while True:
                    command, payload = self.items.get()
                    if command == "row":
                        serialized = {
                            key: 1 if value is True else 0 if value is False else value
                            for key, value in payload.items()
                        }
                        writer.writerow(serialized)
                        handle.flush()
                    elif command == "checkpoint":
                        handle.flush()
                        os.fsync(handle.fileno())
                        payload.set()
                    elif command == "stop":
                        handle.flush()
                        os.fsync(handle.fileno())
                        return
        except BaseException as exc:
            self.error = exc
            self.ready.set()

    def _raise_if_error(self):
        if self.error is not None:
            raise RuntimeError("The trial writer failed") from self.error

    def submit(self, row):
        self._raise_if_error()
        self.items.put(("row", row))

    def checkpoint(self):
        self._raise_if_error()
        completed = threading.Event()
        self.items.put(("checkpoint", completed))
        while not completed.wait(0.05):
            self._raise_if_error()
            if not self.thread.is_alive():
                raise RuntimeError("The trial writer stopped unexpectedly")

    def close(self):
        if self.thread.is_alive():
            self.items.put(("stop", None))
            self.thread.join()
        self._raise_if_error()


def draw_base_scene(background_stim, reference_stim, center_stim=None):
    background_stim.draw()
    reference_stim.draw()
    if center_stim is not None:
        center_stim.draw()


def wait_for_space_release(kb, key_event_recorder=None):
    while kb.getState("space"):
        if key_event_recorder is not None:
            downs, _ups = key_event_recorder.poll(kb)
            if any(press["key"] == "escape" for press in downs):
                raise ExperimentAbort()
        elif kb.getKeys(keyList=["escape"], waitRelease=False, clear=True):
            raise ExperimentAbort()
        core.wait(0.01)
    if key_event_recorder is None:
        kb.clearEvents()


def show_gate(
    win,
    kb,
    background_stim,
    reference_stim,
    title,
    body,
    ui_scale=1.0,
    key_text="SPACE",
    key_event_recorder=None,
):
    panel = visual.Rect(
        win,
        width=980 * ui_scale,
        height=390 * ui_scale,
        pos=(0, 20 * ui_scale),
        fillColor="#123f36",
        lineColor="#f4b942",
        lineWidth=max(1, 3 * ui_scale),
        opacity=0.94,
        units="pix",
    )
    title_stim = visual.TextStim(
        win,
        text=title,
        font="Malgun Gothic",
        height=50 * ui_scale,
        pos=(0, 0 if not body and not key_text else 110 * ui_scale),
        color="#fffdf6",
        bold=True,
        units="pix",
    )
    body_stim = visual.TextStim(
        win,
        text=body,
        font="Malgun Gothic",
        height=31 * ui_scale,
        pos=(0, 0),
        color="#d9f3e8",
        wrapWidth=850 * ui_scale,
        units="pix",
    )
    key_stim = visual.TextStim(
        win,
        text=key_text,
        font="Segoe UI",
        height=34 * ui_scale,
        pos=(0, -140 * ui_scale),
        color="#ffe09a",
        bold=True,
        units="pix",
    )

    draw_base_scene(background_stim, reference_stim)
    panel.draw()
    title_stim.draw()
    body_stim.draw()
    key_stim.draw()
    win.flip()

    wait_for_space_release(kb, key_event_recorder)
    while True:
        if key_event_recorder is not None:
            downs, _ups = key_event_recorder.poll(kb)
            key_names = [press["key"] for press in downs]
        else:
            keys = kb.getKeys(
                keyList=["space", "escape"],
                waitRelease=False,
                clear=True,
            )
            key_names = [key.name for key in keys]
        for key_name in key_names:
            if key_name == "escape":
                raise ExperimentAbort()
            if key_name == "space":
                wait_for_space_release(kb, key_event_recorder)
                return
        core.wait(0.01)


def show_loading(win, background_stim, reference_stim, phase, ui_scale=1.0):
    loading_text = visual.TextStim(
        win,
        text=f"{phase} 카드를 불러오고 있습니다...",
        font="Malgun Gothic",
        height=36 * ui_scale,
        color="#fffdf6",
        pos=(0, 0),
        units="pix",
    )
    draw_base_scene(background_stim, reference_stim)
    loading_text.draw()
    win.flip()


def show_practice_result(
    win,
    kb,
    background_stim,
    reference_stim,
    summary,
    title,
    message,
    ui_scale=1.0,
):
    def bar(correct, total, width=20):
        filled = int(round(width * correct / total)) if total else 0
        return "█" * filled + "░" * (width - filled)

    panel = visual.Rect(
        win,
        width=1140 * ui_scale,
        height=650 * ui_scale,
        pos=(0, 0),
        fillColor="#123f36",
        lineColor="#f4b942",
        lineWidth=max(1, 3 * ui_scale),
        opacity=0.96,
        units="pix",
    )
    title_stim = visual.TextStim(
        win,
        text=title,
        font="Malgun Gothic",
        height=48 * ui_scale,
        pos=(0, 220 * ui_scale),
        color="#fffdf6",
        bold=True,
        units="pix",
    )
    score_text = (
        f"같은 카드     {summary['target_correct']} / {summary['target_total']}  "
        f"{bar(summary['target_correct'], summary['target_total'])}\n"
        f"다른 카드     {summary['nogo_correct']} / {summary['nogo_total']}  "
        f"{bar(summary['nogo_correct'], summary['nogo_total'])}\n"
        f"전체 정답     {summary['overall_correct']} / {summary['overall_total']}  "
        f"{bar(summary['overall_correct'], summary['overall_total'])}"
    )
    score_stim = visual.TextStim(
        win,
        text=score_text,
        font="Malgun Gothic",
        height=31 * ui_scale,
        pos=(0, 55 * ui_scale),
        color="#d9f3e8",
        alignText="left",
        anchorHoriz="center",
        wrapWidth=980 * ui_scale,
        units="pix",
    )
    message_stim = visual.TextStim(
        win,
        text=message,
        font="Malgun Gothic",
        height=29 * ui_scale,
        pos=(0, -145 * ui_scale),
        color="#ffe09a",
        wrapWidth=940 * ui_scale,
        units="pix",
    )
    key_stim = visual.TextStim(
        win,
        text="SPACE",
        font="Segoe UI",
        height=32 * ui_scale,
        pos=(0, -255 * ui_scale),
        color="#fffdf6",
        bold=True,
        units="pix",
    )

    draw_base_scene(background_stim, reference_stim)
    panel.draw()
    title_stim.draw()
    score_stim.draw()
    message_stim.draw()
    key_stim.draw()
    win.flip()

    wait_for_space_release(kb)
    while True:
        keys = kb.getKeys(keyList=["space", "escape"], waitRelease=False, clear=True)
        for key in keys:
            if key.name == "escape":
                raise ExperimentAbort()
            if key.name == "space":
                wait_for_space_release(kb)
                return
        core.wait(0.01)


def prepare_block_stimuli(
    win,
    block,
    stimulus_position,
    stimulus_size,
    target_position,
    target_size,
):
    unique_paths = sorted({trial["image_path"] for trial in block["trials"]})
    center_stimuli = {}
    for path in unique_paths:
        center_stimuli[path] = visual.ImageStim(
            win,
            image=str(path),
            pos=stimulus_position,
            size=stimulus_size,
            units="pix",
            interpolate=True,
        )
    reference_stim = visual.ImageStim(
        win,
        image=str(block["set_info"]["target_path"]),
        pos=target_position,
        size=target_size,
        units="pix",
        interpolate=True,
    )
    return center_stimuli, reference_stim


def locate_key_trial(key_rt, trial_onsets, runtime_rows, trial_seconds):
    if key_rt is None or not trial_onsets:
        return None
    trial_index = bisect_right(trial_onsets, key_rt) - 1
    if trial_index < 0 or trial_index >= len(runtime_rows):
        return None
    relative_rt = key_rt - trial_onsets[trial_index]
    boundary_epsilon = 1e-9
    if (
        relative_rt < -boundary_epsilon
        or relative_rt >= trial_seconds - boundary_epsilon
    ):
        return None
    return trial_index, max(0.0, relative_rt)


def process_key_events(
    kb,
    trial_onsets,
    runtime_rows,
    open_presses,
    timing,
    key_event_recorder=None,
):
    if key_event_recorder is None:
        raise RuntimeError("A PhysicalKeyTracker is required")
    new_downs, _completed_ups = key_event_recorder.poll(kb)
    for press in new_downs:
        if press["key"] == "escape":
            raise ExperimentAbort()
        if press["key"] != "space":
            continue
        location = locate_key_trial(
            press["keydown_abs_s"],
            trial_onsets,
            runtime_rows,
            timing.trial_seconds,
        )
        if location is None:
            continue
        trial_index, relative_rt = location
        press["keydown_trial_s"] = float(relative_rt)
        runtime_rows[trial_index]["key_events"].append(press)
    return list(key_event_recorder.open_by_key.values())


def evaluate_trial(
    trial,
    runtime_row,
    trial_end_block_s,
    timing,
):
    events = sorted(runtime_row["key_events"], key=lambda item: item["keydown_trial_s"])
    primary = events[0] if events else None
    responded = primary is not None
    rt_seconds = primary["keydown_trial_s"] if primary else None
    anticipatory = responded and rt_seconds < timing.premature_seconds
    space_held_at_onset = bool(runtime_row.get("space_held_at_onset", False))
    valid_for_analysis = not anticipatory
    response_required = trial["stimulus_type"] == TARGET

    if anticipatory:
        correct = ""
        error_type = ""
        exclusion_reasons = (
            f"anticipatory_lt_{int(round(timing.premature_seconds * 1000))}ms"
        )
    elif response_required and responded:
        correct = True
        error_type = ""
        exclusion_reasons = ""
    elif response_required:
        correct = False
        error_type = "go_omission"
        exclusion_reasons = ""
    elif responded:
        correct = False
        error_type = "commission"
        exclusion_reasons = ""
    else:
        correct = True
        error_type = ""
        exclusion_reasons = ""

    runtime_row.update({
        "trial_end_block_s": trial_end_block_s,
        "responded": responded,
        "response_key": "space" if responded else "",
        "response_count": len(events),
        "additional_space_count": max(0, len(events) - 1),
        "rt_ms": round(rt_seconds * 1000, 3) if rt_seconds is not None else "",
        "anticipatory": anticipatory,
        "valid_for_analysis": valid_for_analysis,
        "correct": correct,
        "error_type": error_type,
        "exclusion_reasons": exclusion_reasons,
        "keydown_ms": round(primary["keydown_trial_s"] * 1000, 3) if primary else "",
        "keyup_ms": (
            round(
                (primary["keyup_abs_s"] - runtime_row["onset_abs_s"]) * 1000,
                3,
            )
            if primary and primary["keyup_abs_s"] is not None else ""
        ),
        "press_duration_ms": (
            round(primary["duration_s"] * 1000, 3)
            if primary and primary["duration_s"] is not None else ""
        ),
        # Keep this mutable until the row is written. A key release can arrive
        # after the response window and must still be attached to this event.
        "key_events": events,
    })
    return runtime_row


def run_block(
    win,
    kb,
    session_clock,
    background_stim,
    reference_stim,
    center_stimuli,
    block,
    refresh_hz,
    timing,
    on_trial_complete,
    key_event_recorder=None,
):
    stimulus_frames = int(round(timing.stimulus_seconds * refresh_hz))
    trial_frames = int(round(timing.trial_seconds * refresh_hz))
    if stimulus_frames <= 0 or trial_frames <= stimulus_frames:
        raise RuntimeError("Invalid frame counts for the measured refresh rate")

    runtime_rows = [
        {
            "key_events": [],
            "onset_block_s": None,
            "onset_abs_s": None,
            "onset_session_s": None,
            "stimulus_offset_block_s": None,
            "trial_end_block_s": None,
            "space_held_at_onset": False,
        }
        for _ in block["trials"]
    ]
    trial_onsets = []
    block_clock = core.Clock()
    open_presses = []
    first_flip = True
    next_to_save = 0

    def save_ready_trials(force=False):
        nonlocal next_to_save
        while next_to_save < len(runtime_rows):
            runtime = runtime_rows[next_to_save]
            if runtime["trial_end_block_s"] is None:
                break
            trial = block["trials"][next_to_save]
            evaluate_trial(
                trial, runtime, runtime["trial_end_block_s"], timing
            )
            on_trial_complete(trial, runtime, stimulus_frames, trial_frames)
            next_to_save += 1

    def poll_key_events():
        nonlocal open_presses
        try:
            open_presses = process_key_events(
                kb,
                trial_onsets,
                runtime_rows,
                open_presses,
                timing,
                key_event_recorder,
            )
        except ExperimentAbort:
            save_ready_trials(force=True)
            raise

    # Re-establish a steady flip cadence after the SPACE gate has been static.
    # This keeps the first trial of each block on the same timing footing as
    # the trials that follow it. No center stimulus is shown or logged here.
    warmup_frames = max(1, int(round(0.2 * refresh_hz)))
    for _ in range(warmup_frames):
        draw_base_scene(background_stim, reference_stim)
        win.flip()

    for trial_index, trial in enumerate(block["trials"]):
        center_stim = center_stimuli[trial["image_path"]]
        for frame_index in range(trial_frames):
            draw_base_scene(
                background_stim,
                reference_stim,
                center_stim if frame_index < stimulus_frames else None,
            )

            if first_flip:
                win.callOnFlip(block_clock.reset)
            if frame_index == 0:
                def mark_trial_onset(runtime=runtime_rows[trial_index]):
                    onset_session_s = session_clock.getTime()
                    runtime["onset_session_s"] = onset_session_s
                    runtime["onset_abs_s"] = (
                        session_clock.getLastResetTime() + onset_session_s
                    )
                win.callOnFlip(mark_trial_onset)

            win.flip()

            if frame_index == 0:
                onset_block_s = block_clock.getTime()
                onset_abs_s = runtime_rows[trial_index]["onset_abs_s"]
                trial_onsets.append(onset_abs_s)
                runtime_rows[trial_index]["onset_block_s"] = onset_block_s
                runtime_rows[trial_index]["space_held_at_onset"] = bool(
                    kb.getState("space")
                )
                if trial_index > 0:
                    runtime_rows[trial_index - 1]["trial_end_block_s"] = onset_block_s
            elif frame_index == stimulus_frames:
                runtime_rows[trial_index]["stimulus_offset_block_s"] = (
                    block_clock.getTime()
                )

            poll_key_events()
            first_flip = False

    draw_base_scene(background_stim, reference_stim)
    win.flip()
    final_boundary = block_clock.getTime()
    runtime_rows[-1]["trial_end_block_s"] = final_boundary
    poll_key_events()

    save_ready_trials(force=True)
    if next_to_save != len(runtime_rows):
        raise RuntimeError("Not every completed trial was queued for saving")

    return stimulus_frames, trial_frames


def run_practice_block(
    win,
    kb,
    session_clock,
    background_stim,
    reference_stim,
    center_stimuli,
    block,
    refresh_hz,
    response_timing,
    feedback_seconds,
    on_trial_complete,
    ui_scale=1.0,
    key_event_recorder=None,
):
    stimulus_frames = int(round(response_timing.stimulus_seconds * refresh_hz))
    response_frames = int(round(response_timing.trial_seconds * refresh_hz))
    if stimulus_frames <= 0 or response_frames != stimulus_frames:
        raise RuntimeError(
            "Practice requires the stimulus and response window to have equal frames"
        )

    correct_feedback = visual.TextStim(
        win,
        text="정답입니다",
        font="Malgun Gothic",
        height=46 * ui_scale,
        color="#1d8a55",
        bold=True,
        pos=(0, 0),
        units="pix",
    )
    feedback_panel = visual.Rect(
        win,
        width=460 * ui_scale,
        height=150 * ui_scale,
        pos=(0, 0),
        fillColor="#fffdf6",
        lineColor="#d6c8ab",
        lineWidth=max(1, 2 * ui_scale),
        opacity=0.97,
        units="pix",
    )
    incorrect_feedback = visual.TextStim(
        win,
        text="오답입니다",
        font="Malgun Gothic",
        height=46 * ui_scale,
        color="#c23b3b",
        bold=True,
        pos=(0, 0),
        units="pix",
    )

    runtime_rows = []
    trial_onsets = []
    block_clock = core.Clock()
    open_presses = []
    first_flip = True
    next_to_save = 0

    def save_ready_trials(force=False):
        nonlocal next_to_save
        while next_to_save < len(runtime_rows):
            runtime = runtime_rows[next_to_save]
            if (
                runtime["trial_end_block_s"] is None
                or runtime["actual_cycle_duration_s"] is None
            ):
                break
            trial = block["trials"][next_to_save]
            evaluate_trial(
                trial,
                runtime,
                runtime["trial_end_block_s"],
                response_timing,
            )
            on_trial_complete(
                trial,
                runtime,
                stimulus_frames,
                response_frames,
                feedback_seconds,
            )
            next_to_save += 1

    warmup_frames = max(1, int(round(0.2 * refresh_hz)))
    for _ in range(warmup_frames):
        draw_base_scene(background_stim, reference_stim)
        win.flip()

    for trial_index, trial in enumerate(block["trials"]):
        runtime = {
            "key_events": [],
            "onset_block_s": None,
            "onset_abs_s": None,
            "onset_session_s": None,
            "stimulus_offset_block_s": None,
            "trial_end_block_s": None,
            "feedback_duration_ms": feedback_seconds * 1000,
            "actual_cycle_duration_s": None,
            "space_held_at_onset": False,
        }
        runtime_rows.append(runtime)
        center_stim = center_stimuli[trial["image_path"]]

        for frame_index in range(response_frames):
            draw_base_scene(background_stim, reference_stim, center_stim)
            if first_flip:
                win.callOnFlip(block_clock.reset)
            if frame_index == 0:
                def mark_trial_onset(runtime=runtime):
                    onset_session_s = session_clock.getTime()
                    runtime["onset_session_s"] = onset_session_s
                    runtime["onset_abs_s"] = (
                        session_clock.getLastResetTime() + onset_session_s
                    )
                win.callOnFlip(mark_trial_onset)
            win.flip()
            if frame_index == 0:
                onset_block_s = block_clock.getTime()
                onset_abs_s = runtime["onset_abs_s"]
                trial_onsets.append(onset_abs_s)
                runtime["onset_block_s"] = onset_block_s
                runtime["space_held_at_onset"] = bool(kb.getState("space"))
            open_presses = process_key_events(
                kb,
                trial_onsets,
                runtime_rows,
                open_presses,
                response_timing,
                key_event_recorder,
            )
            first_flip = False

        draw_base_scene(background_stim, reference_stim)
        win.flip()
        response_boundary = block_clock.getTime()
        runtime["stimulus_offset_block_s"] = response_boundary
        runtime["trial_end_block_s"] = response_boundary
        open_presses = process_key_events(
            kb,
            trial_onsets,
            runtime_rows,
            open_presses,
            response_timing,
            key_event_recorder,
        )
        evaluate_trial(
            trial,
            runtime,
            response_boundary,
            response_timing,
        )

        if runtime["correct"]:
            feedback_stim = correct_feedback
        else:
            feedback_stim = incorrect_feedback

        draw_base_scene(background_stim, reference_stim)
        feedback_panel.draw()
        feedback_stim.draw()
        win.flip()
        feedback_clock = core.Clock()
        while feedback_clock.getTime() < feedback_seconds:
            core.wait(0.005)
            open_presses = process_key_events(
                kb,
                trial_onsets,
                runtime_rows,
                open_presses,
                response_timing,
                key_event_recorder,
            )

        runtime["actual_cycle_duration_s"] = (
            block_clock.getTime() - runtime["onset_block_s"]
        )
        evaluate_trial(trial, runtime, response_boundary, response_timing)

    save_ready_trials(force=True)
    if next_to_save != len(runtime_rows):
        raise RuntimeError("Not every completed practice trial was queued for saving")
    return runtime_rows


def summarize_practice(block, runtime_rows):
    target_total = sum(
        trial["stimulus_type"] == TARGET for trial in block["trials"]
    )
    target_correct = sum(
        trial["stimulus_type"] == TARGET and runtime["correct"] is True
        for trial, runtime in zip(block["trials"], runtime_rows)
    )
    nogo_total = len(block["trials"]) - target_total
    nogo_correct = sum(
        trial["stimulus_type"] != TARGET and runtime["correct"] is True
        for trial, runtime in zip(block["trials"], runtime_rows)
    )
    overall_total = len(block["trials"])
    overall_correct = target_correct + nogo_correct
    target_passed = target_correct >= 4
    nogo_passed = nogo_correct >= 8
    overall_passed = overall_correct >= 12
    return {
        "target_correct": target_correct,
        "target_total": target_total,
        "nogo_correct": nogo_correct,
        "nogo_total": nogo_total,
        "overall_correct": overall_correct,
        "overall_total": overall_total,
        "target_passed": target_passed,
        "nogo_passed": nogo_passed,
        "overall_passed": overall_passed,
        "practice_passed": target_passed and nogo_passed and overall_passed,
    }


def make_runtime_row(
    subject_info,
    seed,
    selection,
    trial,
    runtime,
    refresh_hz,
    stimulus_frames,
    trial_frames,
    timing,
    target_selection_mode,
    project_dir,
):
    onset = runtime["onset_block_s"]
    offset = runtime["stimulus_offset_block_s"]
    return {
        "subject": subject_info["SubIdx"],
        "session": subject_info["SubSes"],
        "subject_type": subject_info["SubType"],
        "date": subject_info["date"],
        "session_seed": seed,
        "counterbalance_cell_id": trial.get("counterbalance_cell_id", ""),
        "onset_session_ms": round(runtime["onset_session_s"] * 1000, 3),
        "overall_trial_number": trial["global_trial_index"],
        "block_index": trial["block_index"],
        "block_type": trial["block_type"],
        "within_block_trial_number": trial["block_trial_index"],
        "target_set": trial["target_set"],
        "target_pattern_id": trial["target_pattern_id"],
        "stimulus_pattern_id": trial["stimulus_pattern_id"],
        "stimulus_type": trial["stimulus_type"],
        "position_in_dominant_run": trial.get("position_in_dominant_run", ""),
        "nogo_count_since_last_target": trial.get(
            "nogo_count_since_last_target", ""
        ),
        "response_required": trial["stimulus_type"] == TARGET,
        "responded": runtime["responded"],
        "response_key": runtime["response_key"],
        "response_count": runtime["response_count"],
        "additional_space_count": runtime["additional_space_count"],
        "correct": runtime["correct"],
        "press_duration": runtime["press_duration_ms"],
        "rt_ms": runtime["rt_ms"],
        "error_type": runtime["error_type"],
        "valid_for_analysis": runtime["valid_for_analysis"],
        "too_early_response": runtime["anticipatory"],
        "exclusion_reasons": runtime["exclusion_reasons"],
        "scheduled_stimulus_duration_ms": timing.stimulus_seconds * 1000,
        "actual_stimulus_duration_ms": round((offset - onset) * 1000, 3),
        "response_window_ms": timing.trial_seconds * 1000,
        "actual_trial_duration_ms": round(
            (runtime["trial_end_block_s"] - onset) * 1000, 3
        ),
        "refresh_hz": round(refresh_hz, 4),
        "stimulus_frames": stimulus_frames,
        "trial_frames": trial_frames,
        "image_path": str(Path(trial["image_path"]).relative_to(project_dir)),
    }
