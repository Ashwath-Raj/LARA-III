"""Replaceable inference adapters and a policy-enforcing provider boundary."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .models import AccessContext, Actor, DecisionKind
from .policy import ACTION_RISK, PolicyEngine
from .provider_config import ProviderConfig
from .services import PolicyDeniedError


class ProviderError(Exception):
    code = "PROVIDER_ERROR"


class ProviderUnavailableError(ProviderError):
    code = "PROVIDER_UNAVAILABLE"


class ProviderAuthenticationError(ProviderError):
    code = "PROVIDER_AUTHENTICATION_FAILED"


class ProviderTimeoutError(ProviderError):
    code = "PROVIDER_TIMEOUT"


class ProviderResponseError(ProviderError):
    code = "PROVIDER_INVALID_RESPONSE"


class ProviderConfigurationError(ProviderError):
    code = "PROVIDER_CONFIGURATION_ERROR"


@dataclass(frozen=True)
class GenerationResult:
    provider_id: str
    model_id: str
    text: str


class InferenceAdapter(Protocol):
    provider_id: str
    model_id: str

    def generate_text(self, prompt: str, *, response_schema: dict[str, Any] | None = None) -> GenerationResult: ...


TASK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"}, "description": {"type": "string"},
        "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
        "category": {"type": "string"}, "due_date": {"type": ["string", "null"]},
        "due_at": {"type": ["string", "null"]}, "timezone": {"type": "string"},
        "item_type": {"type": "string", "enum": ["task", "assignment", "exam", "event", "idea", "follow_up", "research_job", "reminder"]},
    },
    "required": ["title", "description", "priority", "category", "due_date", "due_at", "timezone", "item_type"],
}


def _valid_generation(prompt: str, timeout: float) -> None:
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
        raise ProviderResponseError("Provider request is invalid.")
    if type(timeout) not in (float, int) or not 0.1 <= timeout <= 120:
        raise ProviderConfigurationError("Provider timeout is outside the supported range.")


class OllamaProvider:
    provider_id = "ollama"

    def __init__(self, config: ProviderConfig, transport=None):
        self.model_id = config.ollama_model
        self.timeout = config.ollama_timeout
        self._transport = transport or self._request

    @staticmethod
    def _request(request: urllib.request.Request, timeout: float) -> bytes:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(2_000_001)

    def generate_text(self, prompt: str, *, response_schema: dict[str, Any] | None = None) -> GenerationResult:
        _valid_generation(prompt, self.timeout)
        body: dict[str, Any] = {"model": self.model_id, "prompt": prompt, "stream": False}
        if response_schema is not None:
            body["format"] = response_schema
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            raw = self._transport(request, self.timeout)
        except TimeoutError:
            raise ProviderTimeoutError("Ollama request timed out.") from None
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ProviderAuthenticationError("Ollama authentication failed.") from None
            raise ProviderUnavailableError("Ollama service is unavailable.") from None
        except (urllib.error.URLError, ConnectionError, socket.timeout, OSError) as exc:
            if isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(getattr(exc, "reason", None), socket.timeout):
                raise ProviderTimeoutError("Ollama request timed out.") from None
            raise ProviderUnavailableError("Ollama service is unavailable.") from None
        if not isinstance(raw, bytes) or len(raw) > 2_000_000:
            raise ProviderResponseError("Ollama returned an invalid response.")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderResponseError("Ollama returned an invalid response.") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("response"), str):
            raise ProviderResponseError("Ollama returned an invalid response.")
        if len(payload["response"]) > 1_000_000:
            raise ProviderResponseError("Ollama response exceeded the supported size.")
        return GenerationResult(self.provider_id, self.model_id, payload["response"])


class GeminiProvider:
    provider_id = "gemini"

    def __init__(self, config: ProviderConfig, client=None):
        self.model_id = config.gemini_model
        self.timeout = config.gemini_timeout
        self._api_key = config.gemini_api_key
        self._client = client

    def _client_or_raise(self):
        if not self._api_key:
            raise ProviderConfigurationError("Gemini is not configured: set GEMINI_API_KEY.")
        if self._client is not None:
            return self._client
        try:
            from google import genai
        except ImportError as exc:
            raise ProviderConfigurationError("Gemini SDK is unavailable; install the optional gemini dependency.") from None
        try:
            http_options = genai.types.HttpOptions(
                timeout=int(self.timeout * 1000),
                retry_options=genai.types.HttpRetryOptions(attempts=1))
            self._client = genai.Client(api_key=self._api_key,
                                        http_options=http_options)
        except Exception:
            raise ProviderConfigurationError("Gemini client configuration failed.") from None
        return self._client

    def generate_text(self, prompt: str, *, response_schema: dict[str, Any] | None = None) -> GenerationResult:
        _valid_generation(prompt, self.timeout)
        client = self._client_or_raise()
        try:
            from google.genai import types
        except ImportError:
            types = None
        config: dict[str, Any] = {}
        if response_schema is not None:
            config.update(response_mime_type="application/json", response_json_schema=response_schema)
        try:
            if types is not None:
                response = client.models.generate_content(
                    model=self.model_id, contents=prompt,
                    config=types.GenerateContentConfig(**config) if config else None)
            else:
                response = client.models.generate_content(model=self.model_id, contents=prompt,
                                                          config=config or None)
        except TimeoutError:
            raise ProviderTimeoutError("Gemini request timed out.") from None
        except Exception as exc:
            # Avoid exception text: SDK errors may contain request bodies or credential details.
            name = type(exc).__name__.lower()
            code = getattr(exc, "code", None)
            if code in (401, 403) or "auth" in name or "permission" in name or "unauthorized" in name:
                raise ProviderAuthenticationError("Gemini authentication failed or access was denied.") from None
            if "timeout" in name:
                raise ProviderTimeoutError("Gemini request timed out.") from None
            if "response" in name or "json" in name:
                raise ProviderResponseError("Gemini returned an invalid response.") from None
            raise ProviderUnavailableError("Gemini provider is unavailable.") from None
        try:
            text = getattr(response, "text", None)
        except Exception:
            raise ProviderResponseError("Gemini returned an invalid response.") from None
        if not isinstance(text, str) or len(text) > 1_000_000:
            raise ProviderResponseError("Gemini returned an invalid response.")
        return GenerationResult(self.provider_id, self.model_id, text)


class ProviderRouter:
    """Application boundary: provider calls require trusted policy authorization."""

    def __init__(self, config: ProviderConfig | None = None, policy: PolicyEngine | None = None,
                 ollama: InferenceAdapter | None = None, gemini: InferenceAdapter | None = None):
        self.config = config or ProviderConfig.from_environment()
        self.policy = policy or PolicyEngine()
        self.providers: dict[str, InferenceAdapter] = {
            "ollama": ollama or OllamaProvider(self.config),
            "gemini": gemini or GeminiProvider(self.config),
        }
        self.audit_log: list[dict[str, Any]] = []

    def selected(self, provider: str | None) -> str:
        selected = self.config.default_provider if provider is None else provider
        if not isinstance(selected, str) or selected not in self.providers:
            raise ProviderConfigurationError("Unknown provider selection.")
        return selected

    def _record_audit(self, *, provider: str, action_id: str, reason: str, room_id: str, sensitivity: str,
                      data_categories: list[str], consent: str, outcome: str, duration_ms: float,
                      error: str | None = None) -> None:
        self.audit_log.append({
            "provider": provider,
            "action_id": action_id,
            "reason": reason,
            "destination": "local" if provider == "ollama" else "external",
            "room_id": room_id,
            "sensitivity": sensitivity,
            "data_categories": data_categories,
            "consent": consent,
            "outcome": outcome,
            "duration_ms": duration_ms,
            "error": error,
            "session_id": "local-session",
        })

    def _authorize(self, actor: Actor, *, action_id: str, room_id: str, sensitivity: str,
                   provider: str, resource_id: str) -> None:
        risk = ACTION_RISK.get(action_id)
        if risk is None:
            raise PolicyDeniedError("Access denied.")
        destination = "local" if provider == "ollama" else "gemini"
        decision = self.policy.evaluate_access(AccessContext(
            actor.principal_id, actor.persona_id, None, room_id, resource_id, action_id,
            sensitivity, destination, risk.value, "normal"))
        if decision.decision != DecisionKind.ALLOW:
            raise PolicyDeniedError("Provider request is not authorized by local policy.")

    def _ensure_authorized(self, actor: Actor, *, provider: str | None, action_id: str,
                           room_id: str, sensitivity: str, resource_id: str,
                           cloud_opt_in: bool = False) -> str:
        selected = self.selected(provider)
        if not isinstance(actor, Actor):
            raise PolicyDeniedError("Provider request is not authorized by local policy.")
        if selected == "gemini" and action_id != "provider.health_check" and not self.config.can_route_cloud(
                explicit_opt_in=cloud_opt_in, provider=selected):
            raise PolicyDeniedError("Hosted inference requires explicit opt-in and a configured external fallback policy.")
        self._authorize(actor, action_id=action_id, room_id=room_id, sensitivity=sensitivity,
                        provider=selected, resource_id=resource_id)
        return selected

    def authorize_task_capture(self, actor: Actor, *, provider: str | None,
                               cloud_opt_in: bool = False) -> str:
        return self._ensure_authorized(actor, provider=provider, action_id="task.capture",
                                       room_id="operations", sensitivity="internal",
                                       resource_id="task-capture-preview", cloud_opt_in=cloud_opt_in)

    def generate_task_capture(self, prompt: str, actor: Actor, *, provider: str | None = None,
                              response_schema: dict[str, Any] | None = None,
                              cloud_opt_in: bool = False) -> GenerationResult:
        selected = self.authorize_task_capture(actor, provider=provider, cloud_opt_in=cloud_opt_in)
        # Policy is evaluated before the adapter receives the prompt.
        started = time.perf_counter()
        try:
            result = self.providers[selected].generate_text(prompt, response_schema=response_schema)
            self._record_audit(provider=selected, action_id="task.capture", reason="task preview generation",
                              room_id="operations", sensitivity="internal", data_categories=["task_text"],
                              consent="explicit" if selected == "ollama" else "opt_in" if cloud_opt_in else "denied",
                              outcome="success", duration_ms=(time.perf_counter() - started) * 1000)
            return result
        except ProviderError as exc:
            self._record_audit(provider=selected, action_id="task.capture", reason="task preview generation",
                              room_id="operations", sensitivity="internal", data_categories=["task_text"],
                              consent="explicit" if selected == "ollama" else "opt_in" if cloud_opt_in else "denied",
                              outcome="error", duration_ms=(time.perf_counter() - started) * 1000,
                              error=f"{type(exc).__name__}: {str(exc)[:200]}")
            raise

    def health_check(self, provider: str | None, actor: Actor) -> GenerationResult:
        selected = self.selected(provider)
        # Generic fixed prompt: no user task text or database data is sent.
        selected = self._ensure_authorized(actor, provider=selected, action_id="provider.health_check",
                                           room_id="public_research", sensitivity="public",
                                           resource_id="generic-health-check", cloud_opt_in=selected == "gemini")
        started = time.perf_counter()
        try:
            result = self.providers[selected].generate_text("Reply with the single word OK.")
            self._record_audit(provider=selected, action_id="provider.health_check", reason="connectivity verification",
                              room_id="public_research", sensitivity="public", data_categories=["metadata_only"],
                              consent="automatic" if selected == "ollama" else "opt_in",
                              outcome="success", duration_ms=(time.perf_counter() - started) * 1000)
            return result
        except ProviderError as exc:
            self._record_audit(provider=selected, action_id="provider.health_check", reason="connectivity verification",
                              room_id="public_research", sensitivity="public", data_categories=["metadata_only"],
                              consent="automatic" if selected == "ollama" else "opt_in",
                              outcome="error", duration_ms=(time.perf_counter() - started) * 1000,
                              error=f"{type(exc).__name__}: {str(exc)[:200]}")
            raise
