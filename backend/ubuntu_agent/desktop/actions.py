"""Allowlisted desktop action vocabulary. Model text never becomes a shell command."""

from __future__ import annotations

from urllib.parse import urlparse

from ubuntu_agent.services import ValidationError

ALLOWED_ACTIONS = (
    "focus_window", "open_url", "move_pointer", "click_target", "type_text", "paste_text",
    "scroll_window", "capture_screenshot", "wait_for_state", "tile_windows", "request_user_confirmation",
)
CONSEQUENTIAL_INTENTS = frozenset({
    "send_message", "publish", "submit_form", "delete_data", "change_account", "purchase",
})
FORBIDDEN_FIELD_HINTS = ("password", "otp", "mfa", "captcha", "2fa", "one-time")
MAX_TEXT = 4000
SLOT_NAMES = ("nw", "ne", "sw", "se")


def validate_url(url: object) -> str:
    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        raise ValidationError("URL is invalid.")
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValidationError("Only http(s) URLs without credentials are permitted.")
    host = parsed.hostname or ""
    if host.endswith(".onion") or host in {"0.0.0.0"}:
        raise ValidationError("URL host is not permitted.")
    return url.strip()


def validate_action(action: object) -> dict:
    if not isinstance(action, dict):
        raise ValidationError("Desktop action must be an object.")
    name = action.get("type")
    if name not in ALLOWED_ACTIONS:
        raise ValidationError("Desktop action is not in the allowlist.")
    if any(key in action for key in ("shell", "command", "executable", "python", "script", "argv")):
        raise ValidationError("Arbitrary process execution is not a desktop action.")
    slot = action.get("slot")
    if slot is not None and slot not in SLOT_NAMES:
        raise ValidationError("Unknown workspace slot.")
    normalized: dict = {"type": name, "slot": slot}
    if name == "open_url":
        normalized["url"] = validate_url(action.get("url"))
    elif name in {"move_pointer", "click_target"}:
        target = action.get("target") if isinstance(action.get("target"), dict) else action
        for field in ("x", "y"):
            value = target.get(field, action.get(field))
            if type(value) not in (int, float) or isinstance(value, bool):
                raise ValidationError("Pointer coordinates must be finite numbers.")
            normalized[field] = float(value)
        label = action.get("label") or (target.get("label") if isinstance(target, dict) else None)
        if label is not None:
            if not isinstance(label, str) or len(label) > 200:
                raise ValidationError("Target label is invalid.")
            normalized["label"] = label.strip()
        confidence = action.get("confidence", target.get("confidence") if isinstance(target, dict) else 1.0)
        if type(confidence) not in (int, float) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
            raise ValidationError("Confidence must be between 0 and 1.")
        normalized["confidence"] = float(confidence)
        if name == "click_target":
            intent = action.get("intent")
            if intent is not None:
                if not isinstance(intent, str) or intent not in CONSEQUENTIAL_INTENTS | {"navigate", "select", "toggle"}:
                    raise ValidationError("Click intent is invalid.")
                normalized["intent"] = intent
    elif name in {"type_text", "paste_text"}:
        text = action.get("text")
        if not isinstance(text, str) or not text or len(text) > MAX_TEXT:
            raise ValidationError("Input text is missing or too long.")
        field_hint = action.get("field_hint") or ""
        if not isinstance(field_hint, str) or len(field_hint) > 100:
            raise ValidationError("Field hint is invalid.")
        lowered = field_hint.lower()
        if any(token in lowered for token in FORBIDDEN_FIELD_HINTS):
            raise ValidationError("Password, OTP, MFA and CAPTCHA fields cannot be automated.")
        normalized["text_length"] = len(text)
        normalized["text"] = text
        normalized["field_hint"] = field_hint
    elif name == "scroll_window":
        delta = action.get("delta", 0)
        if type(delta) not in (int, float) or isinstance(delta, bool) or abs(float(delta)) > 10000:
            raise ValidationError("Scroll delta is invalid.")
        normalized["delta"] = float(delta)
    elif name == "wait_for_state":
        timeout = action.get("timeout_seconds", 60)
        if type(timeout) not in (int, float) or isinstance(timeout, bool) or not 0.1 <= float(timeout) <= 300:
            raise ValidationError("wait_for_state timeout must be between 0.1 and 300 seconds.")
        expected = action.get("expected") or "ready"
        if not isinstance(expected, str) or len(expected) > 200:
            raise ValidationError("Expected state is invalid.")
        lowered = expected.lower()
        if any(token in lowered for token in FORBIDDEN_FIELD_HINTS):
            raise ValidationError("Authentication and CAPTCHA states require manual user action.")
        normalized["timeout_seconds"] = float(timeout)
        normalized["expected"] = expected
    elif name == "request_user_confirmation":
        prompt = action.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 500:
            raise ValidationError("Confirmation prompt is invalid.")
        normalized["prompt"] = prompt.strip()
        normalized["intent"] = action.get("intent") if action.get("intent") in CONSEQUENTIAL_INTENTS else "select"
    elif name == "focus_window":
        if slot is None:
            raise ValidationError("focus_window requires a slot.")
    elif name == "capture_screenshot":
        normalized["region"] = action.get("region") if action.get("region") in {"window", "desktop"} else "window"
    elif name == "tile_windows":
        pass
    return normalized


def is_consequential(action: dict) -> bool:
    return action.get("type") == "request_user_confirmation" or action.get("intent") in CONSEQUENTIAL_INTENTS
