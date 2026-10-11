"""Typed values shared by the persistence, policy, and domain layers."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class DecisionKind(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRES_APPROVAL = "requires_approval"


class RiskTier(StrEnum):
    READ = "read"
    PREPARE = "prepare"
    REVERSIBLE_WRITE = "reversible_workspace_write"
    EXTERNAL = "external_destructive"
    PRIVILEGED = "privileged_system"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class Actor:
    """Application-resolved caller identity; caller input is never used as a grant."""

    principal_id: str
    persona_id: str


@dataclass(frozen=True)
class AccessContext:
    principal_id: str | None
    persona_id: str | None
    job_id: str | None
    room_id: str | None
    resource_id: str | None
    action_id: str | None
    sensitivity_label: str | None
    destination: str | None
    risk_tier: str | None
    system_mode: str | None
    approval_id: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    decision: DecisionKind
    policy_id: str
    reason: str
    decided_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
