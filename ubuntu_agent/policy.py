"""Deterministic deny-by-default policy evaluator."""

from .bootstrap import PERSONAS, PRINCIPAL_ID
from .models import AccessContext, DecisionKind, PolicyDecision, RiskTier, Sensitivity, utc_now

POLICY_ID = "ubuntu-agent-default-v1"
ACTION_RISK = {
    "task.create": RiskTier.PREPARE,
    "task.read": RiskTier.READ,
    "task.update": RiskTier.PREPARE,
    "task.transition": RiskTier.PREPARE,
    "reminder.create": RiskTier.PREPARE,
    "reminder.read": RiskTier.READ,
    "task.capture": RiskTier.PREPARE,
    "provider.health_check": RiskTier.READ,
    "memory.ingest": RiskTier.PREPARE,
    "memory.search": RiskTier.READ,
    "memory.delete": RiskTier.PREPARE,
    # These names are classified so attempted downgrades are rejected, but no
    # corresponding adapter is registered in this milestone.
    "classroom.submit": RiskTier.EXTERNAL,
    "message.send": RiskTier.EXTERNAL,
    "file.delete": RiskTier.EXTERNAL,
    "system.configure": RiskTier.PRIVILEGED,
    "shell.execute": RiskTier.PRIVILEGED,
}
IMPLEMENTED_ACTIONS = {"task.create", "task.read", "task.update", "task.transition", "reminder.create", "reminder.read",
                       "task.capture", "provider.health_check", "memory.ingest", "memory.search", "memory.delete"}
ROOM_ACCESS = {
    "task_manager": {"operations": "rw", "academic": "r", "projects": "r", "public_research": "r", "opportunities": "r"},
    "study_coach": {"operations": "r", "academic": "rw", "public_research": "r"},
    "researcher": {"operations": "r", "projects": "rw", "public_research": "r", "opportunities": "r"},
    "desktop_operator": {"operations": "r", "academic": "r", "projects": "r", "public_research": "r", "opportunities": "r"},
}
SENSITIVITY_RANK = {label.value: rank for rank, label in enumerate(Sensitivity)}


class PolicyEngine:
    def evaluate_access(self, context: AccessContext) -> PolicyDecision:
        try:
            return self._evaluate_validated(context)
        except Exception:
            # Policy exceptions are a denial, never an implicit allow.
            return self._deny("Policy evaluation failed closed.")

    def _evaluate_validated(self, context: AccessContext) -> PolicyDecision:
        if not isinstance(context, AccessContext):
            return self._deny("Authorization context is malformed.")
        required = (context.principal_id, context.persona_id, context.room_id, context.resource_id,
                    context.action_id, context.sensitivity_label, context.destination,
                    context.risk_tier, context.system_mode)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            return self._deny("Authorization context is incomplete or malformed.")
        if context.job_id is not None or context.approval_id is not None:
            return self._deny("Authorization scope is unsupported.")

        action = ACTION_RISK.get(context.action_id)
        if action is None or context.action_id not in IMPLEMENTED_ACTIONS:
            return self._deny("Action is unknown or unavailable in this milestone.")
        if context.risk_tier not in {risk.value for risk in RiskTier}:
            return self._deny("Risk tier is invalid.")
        if context.risk_tier != action.value:
            return self._deny("Risk tier does not match the registered action.")
        if context.principal_id != PRINCIPAL_ID or context.persona_id not in PERSONAS:
            return self._deny("Identity is not authorized.")
        if context.room_id not in ROOM_ACCESS.get(PERSONAS[context.persona_id][2], {}):
            return self._deny("Room is not authorized.")
        # Operations permissions for non-manager personas are typed/scope limited
        # (deadlines, job state, or active approvals). A room-level grant must
        # never turn those fields into access to arbitrary Operations documents.
        if (context.action_id == "memory.search" and context.room_id == "operations" and
                context.persona_id != "task_deadline_manager"):
            return self._deny("Operations document search is outside this persona's scope.")
        if context.sensitivity_label not in SENSITIVITY_RANK:
            return self._deny("Sensitivity label is invalid.")
        if context.system_mode != "normal":
            return self._deny("Destination or system mode is unavailable.")

        if context.action_id == "provider.health_check":
            # A health check has a fixed, generic prompt and no user content.
            # It is the sole hosted-provider path while disclosure thresholds
            # for real task content remain unresolved.
            if context.destination == "local":
                pass
            elif (context.destination != "gemini" or context.room_id != "public_research"
                  or context.sensitivity_label != "public" or context.persona_id != "task_deadline_manager"):
                return self._deny("Provider health checks are limited to the generic public check.")
        elif context.destination != "local":
            return self._deny("Cloud disclosure is not authorized by the current policy.")

        room_rank = {"public_research": 0, "operations": 1, "academic": 2, "projects": 2,
                     "opportunities": 1, "personal_vault": 3, "health": 3}[context.room_id]
        if SENSITIVITY_RANK[context.sensitivity_label] < room_rank:
            return self._deny("Sensitivity is below the trusted room default.")
        permission = ROOM_ACCESS[PERSONAS[context.persona_id][2]][context.room_id]
        is_write = action != RiskTier.READ
        if permission != "rw" and (permission != "r" or is_write):
            return self._deny("Persona action is not permitted in this room.")
        return PolicyDecision(DecisionKind.ALLOW, POLICY_ID, "Allowed by the default persona and room policy.", utc_now())

    @staticmethod
    def _deny(reason: str) -> PolicyDecision:
        return PolicyDecision(DecisionKind.DENY, POLICY_ID, reason, utc_now())
