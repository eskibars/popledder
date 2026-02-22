from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict

class TextAnimation(IntEnum):
    """Text entrance animation types observed on the 64x64 matrix firmware."""

    APPEAR = 1
    SCROLL_IN_FROM_RIGHT = 2
    SCROLL_IN_FROM_LEFT = 3
    SCROLL_IN_FROM_BOTTOM = 4
    SCROLL_IN_FROM_TOP = 5
    WIPE_LEFT_TO_RIGHT = 6
    WIPE_TOP_TO_BOTTOM = 7
    WIPE_RIGHT_TO_LEFT = 8
    RAINFALL_FROM_TOP = 9
    RAINFALL_FROM_BOTTOM = 10
    RAINFALL_FROM_RIGHT = 11
    ELASTIC_STRETCH_FROM_TOP = 12
    FAST_ELASTIC_STRETCH_FROM_TOP = 13
    FAST_ELASTIC_STRETCH_FROM_BOTTOM = 14
    LASER_SHOOT_FROM_RIGHT = 15
    WIPE_BOTH_SIDES_IN_WITH_LINE = 16
    WIPE_CENTER_OUT_WITH_LINE = 17
    WIPE_LEFT_TO_RIGHT_WITH_LINE = 18
    WIPE_RIGHT_TO_LEFT_WITH_LINE = 19
    INTERLACED_PIXELS_JOIN = 20
    TOP_HALF_LEFT_BOTTOM_HALF_RIGHT = 21
    WIPE_BOTH_SIDES_IN_NO_LINE = 22
    WIPE_CENTER_OUT_NO_LINE = 23
    WIPE_TOP_BOTTOM_IN_NO_LINE = 24
    WIPE_CENTER_OUT_TOP_BOTTOM_NO_LINE = 25
    PARTS_OF_EACH_LETTER_LEFT_RIGHT_SLOW = 28
    PARTS_OF_EACH_LETTER_TOP_BOTTOM = 29
    FLASHING = 30
    FLASHING_INVERT = 31

TEXT_ANIMATION_ALIASES: Dict[str, int] = {
    "appear": 1,
    "scroll_right": 2,
    "scroll_left": 3,
    "scroll_up": 4,
    "scroll_down": 5,
    "wipe_ltr": 6,
    "wipe_ttb": 7,
    "wipe_rtl": 8,
    "rain_top": 9,
    "rain_bottom": 10,
    "rain_right": 11,
    "elastic_top": 12,
    "elastic_top_fast": 13,
    "elastic_bottom_fast": 14,
    "laser_right": 15,
    "wipe_sides_in_line": 16,
    "wipe_center_out_line": 17,
    "wipe_ltr_line": 18,
    "wipe_rtl_line": 19,
    "interlaced_join": 20,
    "half_split_lr": 21,
    "wipe_sides_in": 22,
    "wipe_center_out": 23,
    "wipe_tb_in": 24,
    "wipe_tb_center_out": 25,
    "parts_lr_slow": 28,
    "parts_tb": 29,
    "flash": 30,
    "flash_invert": 31,
}

TEXT_ANIMATION_ALIASES.update({
    "scroll in from the right": 2,
    "scroll in from right": 2,
    "scroll in from the left": 3,
    "scroll in from left": 3,
    "scroll in from the bottom": 4,
    "scroll in from bottom": 4,
    "scroll in from the top": 5,
    "scroll in from top": 5,
})

TEXT_ANIMATION_DESCRIPTIONS: Dict[int, str] = {
    1: 'appear',
    2: 'scroll in from the right',
    3: 'scroll in from the left',
    4: 'scroll in from the bottom',
    5: 'scroll in from the top',
    6: 'wipe in from left to right',
    7: 'wipe in from top to bottom',
    8: 'wipe in from right to left',
    9: 'rainfall style drop in from the top',
    10: 'rainfall style drop in from the bottom',
    11: 'rainfall style drop in from the right',
    12: 'elastic stretch in from the top',
    13: 'fast elastic stretch in from the top',
    14: 'fast elastic stretch in from the bottom',
    15: 'laser shoot in the characters from the right',
    16: 'wipe in from both sides (with vertical lines)',
    17: 'wipe outwards from the middle (with vertical lines)',
    18: 'wipe left to right (with vertical reveal line)',
    19: 'wipe right to left (with vertical reveal line)',
    20: 'interlaced pixels fly in and join',
    21: 'top half flies from left, bottom half from right',
    22: 'wipe in from both sides (no vertical line)',
    23: 'wipe outwards from the middle (no vertical line)',
    24: 'wipe in top+bottom towards center (no line)',
    25: 'wipe outwards from center to top+bottom (no line)',
    28: 'parts of each letter slowly show up left/right',
    29: 'parts of each letter show up top/bottom',
    30: 'flashing text',
    31: 'flashing with inverse (text/background invert)',
}

def normalize_anim_name(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")

def parse_text_animation(value: Any, *, default: int = int(TextAnimation.APPEAR)) -> int:
    if value is None or value == "":
        return int(default)

    if isinstance(value, TextAnimation):
        return int(value)

    try:
        if isinstance(value, int):
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    except Exception:
        pass

    if isinstance(value, str):
        key = normalize_anim_name(value)
        if key.upper() in TextAnimation.__members__:
            return int(TextAnimation[key.upper()])
        if key in TEXT_ANIMATION_ALIASES:
            return int(TEXT_ANIMATION_ALIASES[key])

    return int(default)

def clamp_anim_speed(speed: Any, *, default: int = 9) -> int:
    try:
        s = int(speed)
    except Exception:
        s = int(default)
    return 1 if s < 1 else 15 if s > 15 else s
