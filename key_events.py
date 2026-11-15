# -*- coding: utf-8 -*-
"""Physical keyboard state tracking shared by every task variant."""


KEY_EVENT_FIELDS = [
    "key_event_index",
    "press_id",
    "key",
    "event_type",
    "event_session_ms",
    "repeat",
]


class PhysicalKeyTracker:
    """Convert PsychoPy KeyPress objects into physical UP/DOWN transitions.

    Incomplete KeyPress objects are read without clearing PsychoPy's buffer.
    Completed presses are consumed only after release. Repeated delivery of the
    same object is deduplicated by its absolute keydown time, while a genuinely
    new keydown received in the DOWN state is retained as an OS-repeat event.
    """

    def __init__(self, session_zero_abs_s, submit_row):
        self.session_zero_abs_s = float(session_zero_abs_s)
        self.submit_row = submit_row
        self.seen_keydowns = set()
        self.open_by_key = {}
        self.events = []
        self.presses = []
        self.next_press_id = 1
        self.capture_index = 0
        self.flushed = False

    @staticmethod
    def _absolute_keydown_s(key, clock_reset_abs_s=None):
        if clock_reset_abs_s is not None and getattr(key, "rt", None) is not None:
            return float(clock_reset_abs_s) + float(key.rt)
        t_down = getattr(key, "tDown", None)
        if t_down is None:
            raise ValueError("PsychoPy KeyPress is missing absolute tDown")
        return float(t_down)

    @staticmethod
    def _key_token(key, clock_reset_abs_s=None):
        code = getattr(key, "code", None)
        return (
            str(key.name),
            code,
            PhysicalKeyTracker._absolute_keydown_s(key, clock_reset_abs_s),
        )

    def _session_ms(self, absolute_s):
        return round((float(absolute_s) - self.session_zero_abs_s) * 1000, 3)

    def _capture_event(self, press, event_type, absolute_s, repeat):
        self.events.append({
            "press_id": press["press_id"],
            "key": press["key"],
            "event_type": event_type,
            "event_session_ms": self._session_ms(absolute_s),
            "repeat": repeat,
            "_absolute_s": float(absolute_s),
            "_capture_index": self.capture_index,
        })
        self.capture_index += 1

    def ingest(self, keydowns, completed, clock_reset_abs_s=None):
        """Ingest one poll and return new physical downs and completed ups."""
        candidates = []
        for key in keydowns:
            if getattr(key, "rt", None) is None:
                continue
            token = self._key_token(key, clock_reset_abs_s)
            if token in self.seen_keydowns:
                continue
            self.seen_keydowns.add(token)
            candidates.append((
                self._absolute_keydown_s(key, clock_reset_abs_s),
                0,
                "keydown",
                key,
            ))
        for key in completed:
            duration = getattr(key, "duration", None)
            if getattr(key, "rt", None) is None or duration is None:
                continue
            token = self._key_token(key, clock_reset_abs_s)
            if token not in self.seen_keydowns:
                self.seen_keydowns.add(token)
                candidates.append((
                    self._absolute_keydown_s(key, clock_reset_abs_s),
                    0,
                    "keydown",
                    key,
                ))
            candidates.append((
                self._absolute_keydown_s(key, clock_reset_abs_s) + float(duration),
                1,
                "keyup",
                key,
            ))

        new_downs = []
        completed_ups = []
        for absolute_s, _order, event_type, key in sorted(
            candidates,
            key=lambda item: (item[0], item[1], str(item[3].name)),
        ):
            key_name = str(key.name)
            if event_type == "keydown":
                press = self.open_by_key.get(key_name)
                if press is None:
                    press = {
                        "press_id": self.next_press_id,
                        "key": key_name,
                        "keydown_abs_s": absolute_s,
                        "keyup_abs_s": None,
                        "duration_s": None,
                    }
                    self.next_press_id += 1
                    self.open_by_key[key_name] = press
                    self.presses.append(press)
                    new_downs.append(press)
                    repeat = 0
                else:
                    repeat = 1
                self._capture_event(press, "keydown", absolute_s, repeat)
            else:
                press = self.open_by_key.pop(key_name, None)
                if press is None:
                    # A release without a tracked DOWN is not a physical state
                    # transition in this session and is deliberately ignored.
                    continue
                press["keyup_abs_s"] = absolute_s
                press["duration_s"] = max(
                    0.0,
                    absolute_s - press["keydown_abs_s"],
                )
                self._capture_event(press, "keyup", absolute_s, 0)
                completed_ups.append(press)
        return new_downs, completed_ups

    def poll(self, kb):
        # clear=False is essential: clearing an incomplete press removes the
        # object PsychoPy needs to attach its later release and duration.
        keydowns = kb.getKeys(
            keyList=None,
            waitRelease=False,
            clear=False,
        )
        completed = kb.getKeys(
            keyList=None,
            waitRelease=True,
            clear=True,
        )
        return self.ingest(
            keydowns,
            completed,
            kb.clock.getLastResetTime(),
        )

    def is_down(self, key_name):
        return str(key_name) in self.open_by_key

    def flush(self):
        if self.flushed:
            return
        self.flushed = True
        ordered = sorted(
            self.events,
            key=lambda item: (
                item["_absolute_s"],
                0 if item["event_type"] == "keydown" else 1,
                item["_capture_index"],
            ),
        )
        press_id_by_original = {
            press["press_id"]: index
            for index, press in enumerate(
                sorted(
                    self.presses,
                    key=lambda item: (
                        item["keydown_abs_s"],
                        item["press_id"],
                    ),
                ),
                start=1,
            )
        }
        for event_index, event in enumerate(ordered, start=1):
            self.submit_row({
                "key_event_index": event_index,
                "press_id": press_id_by_original[event["press_id"]],
                "key": event["key"],
                "event_type": event["event_type"],
                "event_session_ms": event["event_session_ms"],
                "repeat": event["repeat"],
            })
