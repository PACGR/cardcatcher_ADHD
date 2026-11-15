# -*- coding: utf-8 -*-
"""Resolution-aware layout helpers shared by CARD CATCHER tasks."""

import ctypes
import json
import math
from pathlib import Path


SUPPORTED_DISPLAY_ASPECTS = {
    "16:10": 16 / 10,
    "16:9": 16 / 9,
}
ASPECT_TOLERANCE = 0.02
MIN_VALID_REFRESH_HZ = 30.0
MAX_VALID_REFRESH_HZ = 500.0


def get_primary_display_size(fallback_size):
    """Return the Windows primary display size, or a validated fallback."""

    fallback = tuple(
        int(round(value))
        for value in _positive_pair(fallback_size, "fallback_size")
    )
    if not hasattr(ctypes, "windll"):
        return fallback
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4)
        )
    except (AttributeError, OSError):
        pass
    try:
        width = int(ctypes.windll.user32.GetSystemMetrics(0))
        height = int(ctypes.windll.user32.GetSystemMetrics(1))
    except (AttributeError, OSError):
        return fallback
    if width <= 0 or height <= 0:
        return fallback
    return width, height


def measure_refresh_hz(win):
    """Measure refresh rate without silently assuming a 60 Hz display."""

    refresh_hz = win.getActualFrameRate(
        nIdentical=20,
        nMaxFrames=240,
        nWarmUpFrames=20,
        threshold=1,
    )
    source = "getActualFrameRate"
    if refresh_hz is None:
        try:
            _mean_ms, _std_ms, median_ms = win.getMsPerFrame(
                nFrames=120,
                showVisual=False,
            )
        except Exception as exc:
            raise RuntimeError(
                "PsychoPy could not measure the monitor refresh rate. "
                "Close background programs and try again."
            ) from exc
        median_ms = float(median_ms)
        if not math.isfinite(median_ms) or median_ms <= 0:
            raise RuntimeError(
                "PsychoPy returned an invalid monitor frame duration."
            )
        refresh_hz = 1000.0 / median_ms
        source = "getMsPerFrame_median"

    refresh_hz = float(refresh_hz)
    if (
        not math.isfinite(refresh_hz)
        or refresh_hz < MIN_VALID_REFRESH_HZ
        or refresh_hz > MAX_VALID_REFRESH_HZ
    ):
        raise RuntimeError(
            f"Measured monitor refresh rate is implausible: "
            f"{refresh_hz:.4f} Hz."
        )
    return refresh_hz, source


def _positive_pair(values, label):
    if len(values) != 2:
        raise ValueError(f"{label} must contain exactly two values")
    pair = tuple(float(value) for value in values)
    if pair[0] <= 0 or pair[1] <= 0:
        raise ValueError(f"{label} values must be positive")
    return pair


def load_cardgame_display_layout(
    actual_screen_size,
    background_path,
    layout_path,
):
    """Load and scale the card-game layout without stretching the background.

    The validated 16:10 background is rendered using a CSS-like ``cover``
    strategy. On 16:9 displays this crops only the unused vertical margins,
    while the background, reference card, and trial card all receive the same
    scale factor.
    """

    screen_width, screen_height = _positive_pair(
        actual_screen_size,
        "actual_screen_size",
    )
    actual_aspect = screen_width / screen_height
    display_profile, expected_aspect = min(
        SUPPORTED_DISPLAY_ASPECTS.items(),
        key=lambda item: abs(actual_aspect - item[1]),
    )
    if abs(actual_aspect - expected_aspect) > ASPECT_TOLERANCE:
        supported = ", ".join(SUPPORTED_DISPLAY_ASPECTS)
        raise RuntimeError(
            f"Unsupported display resolution "
            f"{int(screen_width)}x{int(screen_height)} "
            f"(aspect ratio {actual_aspect:.4f}). "
            f"Supported aspect ratios: {supported}."
        )

    background_path = Path(background_path)
    layout_path = Path(layout_path)
    missing = [
        str(path)
        for path in (background_path, layout_path)
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing card-game display asset(s): " + ", ".join(missing)
        )

    with layout_path.open("r", encoding="utf-8-sig") as handle:
        layout = json.load(handle)

    design_width, design_height = _positive_pair(
        (
            layout["canvas"]["width_px"],
            layout["canvas"]["height_px"],
        ),
        "layout canvas",
    )
    display_scale = max(
        screen_width / design_width,
        screen_height / design_height,
    )
    background_size = (
        design_width * display_scale,
        design_height * display_scale,
    )

    def scaled_pair(section, key):
        return tuple(
            value * display_scale
            for value in _positive_or_signed_pair(layout[section][key], key)
        )

    return {
        "display_profile": display_profile,
        "actual_screen_size": (
            int(round(screen_width)),
            int(round(screen_height)),
        ),
        "actual_aspect_ratio": actual_aspect,
        "layout_canvas_size": (
            int(round(design_width)),
            int(round(design_height)),
        ),
        "display_scale": display_scale,
        "background_size": background_size,
        "horizontal_crop_each_side_px": max(
            0.0,
            (background_size[0] - screen_width) / 2,
        ),
        "vertical_crop_each_side_px": max(
            0.0,
            (background_size[1] - screen_height) / 2,
        ),
        "target_position": scaled_pair(
            "target_card",
            "psychopy_position_px",
        ),
        "target_size": scaled_pair("target_card", "size_px"),
        "stimulus_position": scaled_pair(
            "stimulus_card",
            "psychopy_position_px",
        ),
        "stimulus_size": scaled_pair("stimulus_card", "size_px"),
        "background_path": background_path,
        "layout_path": layout_path,
    }


def _positive_or_signed_pair(values, label):
    if len(values) != 2:
        raise ValueError(f"{label} must contain exactly two values")
    return tuple(float(value) for value in values)


def serializable_display_info(display_layout):
    """Return the display fields that should be persisted in session config."""

    return {
        "display_profile": display_layout["display_profile"],
        "actual_screen_size": list(display_layout["actual_screen_size"]),
        "actual_aspect_ratio": round(
            display_layout["actual_aspect_ratio"],
            6,
        ),
        "layout_canvas_size": list(display_layout["layout_canvas_size"]),
        "display_scale": round(display_layout["display_scale"], 6),
        "background_render_size": [
            round(value, 3)
            for value in display_layout["background_size"]
        ],
        "horizontal_crop_each_side_px": round(
            display_layout["horizontal_crop_each_side_px"],
            3,
        ),
        "vertical_crop_each_side_px": round(
            display_layout["vertical_crop_each_side_px"],
            3,
        ),
        "background_path": str(display_layout["background_path"]),
        "layout_path": str(display_layout["layout_path"]),
    }
