"""Validate visual-target JSON and convert normalized boxes to screen coordinates."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ubuntu_agent.services import ValidationError

MIN_CONFIDENCE = 0.72
MAX_AGE_SECONDS = 8.0


@dataclass(frozen=True)
class GroundedTarget:
    label: str
    x: float
    y: float
    width: float
    height: float
    confidence: float
    reasoning_summary: str
    screen_x: int
    screen_y: int


def parse_grounding_payload(raw: object, *, screenshot_width: int, screenshot_height: int,
                            scale: float = 1.0, observation_age_seconds: float = 0.0,
                            window_id: str | None = None, expected_window_id: str | None = None) -> GroundedTarget:
    if observation_age_seconds > MAX_AGE_SECONDS:
        raise ValidationError("Screenshot observation is stale; capture a new frame before clicking.")
    if type(screenshot_width) is not int or type(screenshot_height) is not int or screenshot_width < 1 or screenshot_height < 1:
        raise ValidationError("Screenshot dimensions are invalid.")
    if type(scale) not in (int, float) or isinstance(scale, bool) or not 0.25 <= float(scale) <= 8:
        raise ValidationError("Display scale is invalid.")
    payload = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise ValidationError("Visual grounding output is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Visual grounding output must be an object.")
    extras = set(payload) - {"label", "bounding_box", "confidence", "reasoning_summary", "window_id", "ambiguous"}
    if extras:
        raise ValidationError("Visual grounding output contains unsupported fields.")
    if payload.get("ambiguous") is True:
        raise ValidationError("Target is ambiguous; ask the user to identify it.")
    label = payload.get("label")
    if not isinstance(label, str) or not label.strip() or len(label) > 200:
        raise ValidationError("Target label is invalid.")
    box = payload.get("bounding_box")
    if not isinstance(box, dict):
        raise ValidationError("Bounding box is required.")
    coords = []
    for key in ("x", "y", "width", "height"):
        value = box.get(key)
        if type(value) not in (int, float) or isinstance(value, bool):
            raise ValidationError("Bounding box values must be numbers.")
        coords.append(float(value))
    x, y, width, height = coords
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 1.0001 or y + height > 1.0001:
        raise ValidationError("Bounding box is outside the screenshot.")
    confidence = payload.get("confidence")
    if type(confidence) not in (int, float) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
        raise ValidationError("Confidence is invalid.")
    if float(confidence) < MIN_CONFIDENCE:
        raise ValidationError("Target confidence is too low to click; ask the user to identify it.")
    summary = payload.get("reasoning_summary")
    if not isinstance(summary, str) or len(summary) > 500:
        raise ValidationError("Reasoning summary is invalid.")
    reported_window = payload.get("window_id")
    if expected_window_id is not None and reported_window not in (None, expected_window_id):
        raise ValidationError("Grounding result does not match the active window.")
    if window_id is not None and expected_window_id is not None and window_id != expected_window_id:
        raise ValidationError("Active window identity does not match the screenshot.")
    cx = (x + width / 2) * screenshot_width * float(scale)
    cy = (y + height / 2) * screenshot_height * float(scale)
    max_x = screenshot_width * float(scale)
    max_y = screenshot_height * float(scale)
    if not (0 <= cx <= max_x and 0 <= cy <= max_y):
        raise ValidationError("Converted coordinates are outside the display.")
    return GroundedTarget(label.strip(), x, y, width, height, float(confidence), summary.strip(),
                          int(round(cx)), int(round(cy)))
