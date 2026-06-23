"""Deterministic colour description helpers for Home Assistant light read-back."""
# Author: Clive Bostock
# Date: 13-Jun-2026
# Description: Classifies live RGB light colours into approximate human labels.

from __future__ import annotations

from collections.abc import Sequence
import colorsys


def describe_rgb_color(rgb: Sequence[int] | None) -> str | None:
    """Return an approximate human description for one RGB colour.

    Args:
        rgb: RGB triplet in 0-255 integer form.

    Returns:
        A conservative colour description, or ``None`` when the colour cannot
        be classified safely.
    """
    rgb_value = _coerce_rgb(rgb)
    if rgb_value is None:
        return None

    red, green, blue = rgb_value
    if red == green == blue:
        return _describe_neutral_rgb(red)

    hue, saturation, value = colorsys.rgb_to_hsv(
        red / 255.0,
        green / 255.0,
        blue / 255.0,
    )
    hue_degrees = hue * 360.0

    if saturation <= 0.35:
        return _describe_low_saturation_rgb(rgb_value, saturation, value)

    base_colour = _describe_hue_band(hue_degrees)
    if base_colour is None:
        return None

    modifier = _describe_modifier(saturation, value)
    if modifier is None:
        return base_colour
    return f"{modifier} {base_colour}"


def _describe_neutral_rgb(level: int) -> str:
    """Return a neutral description for equal-channel RGB values."""
    if level >= 245:
        return "white"
    if level >= 210:
        return "off-white"
    if level >= 160:
        return "grey"
    if level >= 85:
        return "dark grey"
    return "near black"


def _describe_low_saturation_rgb(
    rgb: tuple[int, int, int],
    saturation: float,
    value: float,
) -> str | None:
    """Describe low-saturation colours without over-claiming hue precision."""
    red, green, blue = rgb
    if value <= 0.08:
        return "near black"
    if value <= 0.28:
        return "dark grey"
    if value <= 0.55:
        return "grey"

    warm_bias = red - blue
    cool_bias = blue - red
    green_bias = green - min(red, blue)

    if value >= 0.94:
        if warm_bias >= 28 and green_bias >= 25:
            return "warm cream / pale peach"
        if warm_bias >= 18 and green_bias >= 6:
            return "warm off-white / pale cream"
        if cool_bias >= 18:
            return "cool white / pale blue-white"
        return "white"

    if value >= 0.8:
        if warm_bias >= 28 and green_bias >= 10:
            return "warm cream / pale peach"
        if cool_bias >= 28:
            return "cool white / pale blue-white"
        if saturation <= 0.18:
            return "off-white"
        return "pale off-white"

    if warm_bias >= 20:
        return "warm grey"
    if cool_bias >= 20:
        return "cool grey"
    return "grey"


def _describe_hue_band(hue_degrees: float) -> str | None:
    """Return a safe base colour label for one hue band."""
    if hue_degrees < 0:
        return None
    if hue_degrees < 18 or hue_degrees >= 345:
        return "red"
    if hue_degrees < 45:
        return "orange"
    if hue_degrees < 70:
        return "yellow"
    if hue_degrees < 170:
        return "green"
    if hue_degrees < 205:
        return "cyan"
    if hue_degrees < 255:
        return "blue"
    if hue_degrees < 300:
        return "purple"
    if hue_degrees < 345:
        return "pink / magenta"
    return None


def _describe_modifier(saturation: float, value: float) -> str | None:
    """Return a conservative modifier for hue-based colours."""
    if saturation < 0.22:
        return "soft"
    if value >= 0.88 and saturation >= 0.7:
        return "bright"
    if value <= 0.35:
        return "deep"
    if value <= 0.5:
        return "dark"
    if saturation <= 0.45:
        return "pale"
    if saturation >= 0.8 and value >= 0.6:
        return "vivid"
    return None


def _coerce_rgb(rgb: Sequence[int] | None) -> tuple[int, int, int] | None:
    """Validate and coerce one RGB sequence to a strict integer triplet."""
    if rgb is None or len(rgb) < 3:
        return None
    try:
        red = int(rgb[0])
        green = int(rgb[1])
        blue = int(rgb[2])
    except (TypeError, ValueError):
        return None
    if any(channel < 0 or channel > 255 for channel in (red, green, blue)):
        return None
    return red, green, blue
