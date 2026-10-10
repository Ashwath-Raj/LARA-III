"""Provider configuration with environment-first, secret-safe loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_env_value(name: str) -> str | None:
    """Read one value from the project .env without logging or exporting it."""
    path = Path(__file__).resolve().parent.parent / ".env"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        key, separator, value = stripped.partition("=")
        if not separator or key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value.strip() or None
    return None


def _float_setting(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not 0.1 <= parsed <= 120:
        raise ValueError(f"{name} must be between 0.1 and 120 seconds.")
    return parsed


@dataclass(frozen=True)
class ProviderConfig:
    default_provider: str = "ollama"
    ollama_model: str = "gemma4:e2b-it-q4_K_M"
    ollama_timeout: float = 30.0
    gemini_model: str = "gemma-4-26b-a4b-it"
    gemini_timeout: float = 30.0
    gemini_api_key: str | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_environment(cls) -> "ProviderConfig":
        default_provider = os.environ.get("UBUNTU_AGENT_DEFAULT_PROVIDER", "ollama").strip().lower()
        if default_provider != "ollama":
            raise ValueError("UBUNTU_AGENT_DEFAULT_PROVIDER must be ollama; cloud providers require explicit selection.")
        ollama_model = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-it-q4_K_M").strip()
        gemini_model = os.environ.get("GEMINI_MODEL", "gemma-4-26b-a4b-it").strip()
        if not ollama_model or len(ollama_model) > 200 or not gemini_model or len(gemini_model) > 200:
            raise ValueError("Provider model names must be non-empty and at most 200 characters.")
        return cls(default_provider, ollama_model, _float_setting("OLLAMA_TIMEOUT_SECONDS", 30.0),
                   gemini_model, _float_setting("GEMINI_TIMEOUT_SECONDS", 30.0),
                   (os.environ.get("GEMINI_API_KEY", "").strip() or _project_env_value("GEMINI_API_KEY")))

    @property
    def gemini_sdk_available(self) -> bool:
        try:
            from google import genai  # noqa: F401
        except ImportError:
            return False
        return True

    def provider_status(self) -> dict[str, dict[str, object]]:
        return {
            "ollama": {"configured": True, "model": self.ollama_model, "default": True},
            "gemini": {"configured": bool(self.gemini_api_key and self.gemini_sdk_available),
                       "sdk_available": self.gemini_sdk_available,
                       "api_key_configured": bool(self.gemini_api_key),
                       "model": self.gemini_model, "default": False},
        }
