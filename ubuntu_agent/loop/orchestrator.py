"""Multi-round debate loop with isolated graph/RAG and manual provider handoff."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from ubuntu_agent.bootstrap import PRINCIPAL_ID
from ubuntu_agent.database import Database
from ubuntu_agent.models import AccessContext, Actor, DecisionKind, utc_now
from ubuntu_agent.policy import ACTION_RISK, PolicyEngine
from ubuntu_agent.providers import GenerationResult, InferenceAdapter, ProviderError
from ubuntu_agent.runtime import RuntimeControlService
from ubuntu_agent.services import ConflictError, NotFoundError, PolicyDeniedError, ValidationError

from .graph import LoopGraph
from .role_protocol import INITIAL_STEPS, REVISION_STEPS, ROLE_SCHEMAS, build_role_prompt, parse_role_output

PROVIDER_MODES = {"ollama_api"}
ROLE_NAMES = ("blue_team", "red_team", "judge", "unbiased_reviewer")


def _safe_role_failure_detail(error: Exception) -> str | None:
    """Persist a fixed diagnostic category without retaining model output or exception payloads."""
    if not isinstance(error, ValidationError):
        return None
    message = str(error)
    categories = (
        ("output is malformed", "malformed JSON or oversized output"),
        ("does not match its schema", "required/extra fields do not match the role schema"),
        ("reviewer verdict is invalid", "reviewer verdict is outside the allowed values"),
        ("evidence references are invalid", "Judge citation is missing or not in supplied evidence"),
        ("invalid list data", "role list exceeds its size or item constraints"),
        ("invalid text", "required role text is empty or exceeds its limit"),
    )
    for marker, detail in categories:
        if marker in message:
            return f"Role output failed validation: {detail}."
    return "Role output failed validation against the role contract."
LEASE_SECONDS = 180
ROLE_LABELS = {
    "blue_team": "Blue Team",
    "red_team": "Red Team",
    "judge": "Judge",
    "unbiased_reviewer": "Unbiased Reviewer",
}
OFFICIAL_SITES = {
    "chatgpt_web_assisted": "https://chatgpt.com",
    "gemini_web_assisted": "https://gemini.google.com",
}


class LoopOrchestrator:
    def __init__(self, database: Database, policy: PolicyEngine | None = None, *,
                 ollama: InferenceAdapter | None = None, runtime: RuntimeControlService | None = None,
                 clock: Callable[[], datetime] | None = None):
        self.database = database
        self.policy = policy or PolicyEngine()
        self.ollama = ollama
        self.runtime = runtime or RuntimeControlService(database)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.graph = LoopGraph(database)

    def _now(self) -> str:
        return self.clock().astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _authorize(self, actor: Actor, action_id: str, resource_id: str, *, destination: str = "local",
                   room_id: str = "operations", sensitivity: str = "internal", job_id: str | None = None) -> None:
        if not isinstance(actor, Actor) or actor.principal_id != PRINCIPAL_ID:
            raise PolicyDeniedError("Local user identity is required.")
        risk = ACTION_RISK[action_id]
        decision = self.policy.evaluate_access(AccessContext(
            actor.principal_id, actor.persona_id, job_id, room_id, resource_id, action_id,
            sensitivity, destination, risk.value, "normal"))
        if decision.decision != DecisionKind.ALLOW:
            raise PolicyDeniedError("Current policy denies this action.")

    def _controls_block(self) -> None:
        state = self.runtime.state()
        if state["killed"] or state["paused"]:
            raise PolicyDeniedError("Runtime controls block loop execution.")

    def create_loop(self, actor: Actor, *, goal: str, constraints: list[str] | None = None,
                    provider_mode: str = "ollama_api", cloud_opt_in: bool = False,
                    max_rounds: int = 4, loop_id: str | None = None) -> dict:
        self._authorize(actor, "loop.create", "ai-loop")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 8000:
            raise ValidationError("Loop goal is invalid.")
        if provider_mode not in PROVIDER_MODES:
            raise PolicyDeniedError("The four-role AI Loop currently supports local Ollama inference only.")
        if not isinstance(cloud_opt_in, bool) or cloud_opt_in:
            raise PolicyDeniedError("AI Loop task content is operations-room data and cannot be sent to a hosted provider.")
        if type(max_rounds) is not int or not 4 <= max_rounds <= 12:
            raise ValidationError("max_rounds is a total model-invocation budget between 4 and 12.")
        constraints = constraints or []
        if not isinstance(constraints, list) or len(constraints) > 32:
            raise ValidationError("Constraints are invalid.")
        cleaned = []
        for item in constraints:
            if not isinstance(item, str) or not item.strip() or len(item) > 500:
                raise ValidationError("Constraint text is invalid.")
            cleaned.append(item.strip())
        if loop_id is None:
            loop_id = str(uuid.uuid4())
        else:
            try:
                if str(uuid.UUID(loop_id)) != loop_id:
                    raise ValueError
            except (TypeError, ValueError, AttributeError) as exc:
                raise ValidationError("Loop ID must be a canonical UUID.") from exc
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO ai_loops(id,room_id,persona_id,goal,constraints_json,provider_mode,cloud_opt_in,
                   status,max_rounds,job_id,created_at,updated_at,cancelled_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (loop_id, "operations", actor.persona_id, goal.strip(),
                 json.dumps(cleaned, separators=(",", ":")), provider_mode, 1 if cloud_opt_in else 0,
                 "created", max_rounds, None, now, now))
            for role_name in ROLE_NAMES:
                connection.execute(
                    "INSERT INTO loop_roles(id, loop_id, role_name, role_label, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()), loop_id, role_name, ROLE_LABELS[role_name],
                     "pending", now, now),
                )
            connection.execute(
                """INSERT INTO loop_execution_state
                   (loop_id,status,current_role,current_round,pending_json,invocation_count,
                    created_at,updated_at)
                   VALUES (?,'waiting',NULL,NULL,?,0,?,?)""",
                (loop_id, json.dumps(INITIAL_STEPS, separators=(",", ":")), now, now),
            )
        self.graph.add_node(loop_id, "goal", "User goal", goal.strip(), room_id="operations",
                            sensitivity="internal", provenance={"actor": actor.persona_id})
        for item in cleaned:
            self.graph.add_node(loop_id, "constraint", "Constraint", item, room_id="operations",
                                sensitivity="internal")
        return self.get_loop(loop_id, actor)

    def get_loop(self, loop_id: str, actor: Actor) -> dict:
        self._authorize(actor, "loop.read", loop_id)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM ai_loops WHERE id=?", (loop_id,)).fetchone()
        if row is None:
            raise NotFoundError("Loop not found.")
        payload = dict(row)
        payload["legacy_status"] = payload["status"]
        with self.database.connect() as connection:
            state = connection.execute(
                "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
            ).fetchone()
        if state is None:
            raise NotFoundError("Loop execution state not found.")
        execution = dict(state)
        execution["pending"] = json.loads(execution["pending_json"])
        payload["execution"] = execution
        payload["status"] = execution["status"]
        payload["constraints"] = json.loads(payload["constraints_json"])
        payload["rounds"] = self.list_rounds(loop_id, actor)
        payload["roles"] = self.list_roles(loop_id, actor)
        return payload

    def list_roles(self, loop_id: str, actor: Actor) -> list[dict]:
        self._authorize(actor, "loop.read", loop_id)
        with self.database.connect() as connection:
            if connection.execute("SELECT id FROM ai_loops WHERE id=?", (loop_id,)).fetchone() is None:
                raise NotFoundError("Loop not found.")
            roles = [dict(row) for row in connection.execute(
                "SELECT * FROM loop_roles WHERE loop_id=? ORDER BY role_name", (loop_id,))]
            executions = [dict(row) for row in connection.execute(
                "SELECT * FROM loop_rounds WHERE loop_id=? AND role_name IS NOT NULL ORDER BY round_index",
                (loop_id,),
            )]
        for role in roles:
            role["executions"] = [item for item in executions if item["role_name"] == role["role_name"]]
        return roles

    def list_loops(self, actor: Actor) -> list[dict]:
        self._authorize(actor, "loop.read", "ai-loop")
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT l.id,s.status,l.status AS legacy_status,l.provider_mode,l.goal,l.created_at,l.updated_at
                   FROM ai_loops l JOIN loop_execution_state s ON s.loop_id=l.id ORDER BY l.created_at DESC""")]

    def list_rounds(self, loop_id: str, actor: Actor) -> list[dict]:
        self._authorize(actor, "loop.read", loop_id)
        with self.database.connect() as connection:
            if connection.execute("SELECT id FROM ai_loops WHERE id=?", (loop_id,)).fetchone() is None:
                raise NotFoundError("Loop not found.")
            return [dict(row) for row in connection.execute(
                "SELECT * FROM loop_rounds WHERE loop_id=? ORDER BY round_index", (loop_id,))]

    def cancel(self, loop_id: str, actor: Actor) -> dict:
        self._authorize(actor, "loop.create", loop_id)
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM ai_loops WHERE id=?", (loop_id,)).fetchone()
            if row is None:
                raise NotFoundError("Loop not found.")
            state = connection.execute(
                "SELECT status FROM loop_execution_state WHERE loop_id=?", (loop_id,)
            ).fetchone()
            if state is None:
                raise NotFoundError("Loop not found.")
            if state["status"] not in {"succeeded", "failed", "cancelled", "review_required"}:
                connection.execute(
                    """UPDATE ai_loops SET status='cancelled',cancelled_at=?,updated_at=? WHERE id=?""",
                    (now, now, loop_id),
                )
                connection.execute(
                    """UPDATE loop_execution_state SET status='cancelled',current_role=NULL,current_round=NULL,
                       pending_json='[]',worker_id=NULL,lease_expires_at=NULL,updated_at=? WHERE loop_id=?""",
                    (now, loop_id),
                )
                connection.execute("UPDATE loop_rounds SET status='cancelled',updated_at=? WHERE loop_id=? AND status IN ('queued','running')",
                                   (now, loop_id))
                connection.execute("UPDATE loop_handoffs SET status='cancelled',updated_at=? WHERE loop_id=? AND status='awaiting_user'",
                                   (now, loop_id))
                connection.execute("UPDATE loop_roles SET status='cancelled',updated_at=? WHERE loop_id=? AND status IN ('pending','running')",
                                   (now, loop_id))
        return self.get_loop(loop_id, actor)

    def run_debate(self, loop_id: str, actor: Actor, *, invocation_limit: int | None = None) -> dict:
        return self._execute_loop(loop_id, actor, invocation_limit=invocation_limit, resume=False)

    def resume_loop(self, loop_id: str, actor: Actor, *, invocation_limit: int | None = None) -> dict:
        return self._execute_loop(loop_id, actor, invocation_limit=invocation_limit, resume=True)

    def _execute_loop(self, loop_id: str, actor: Actor, *, invocation_limit: int | None,
                      resume: bool) -> dict:
        if invocation_limit is not None and (type(invocation_limit) is not int or not 1 <= invocation_limit <= 12):
            raise ValidationError("Invocation limit must be between 1 and 12.")
        self._controls_block()
        loop = self.get_loop(loop_id, actor)
        if loop["provider_mode"] != "ollama_api" or loop["cloud_opt_in"]:
            raise PolicyDeniedError("AI Loop execution is restricted to local Ollama inference.")
        adapter = self._adapter_for(loop, actor)
        if resume:
            if loop["status"] not in {"waiting", "running"}:
                raise ConflictError("Loop has no resumable work.")
            if loop["execution"]["invocation_count"] == 0 and loop["status"] == "waiting":
                raise ConflictError("Loop has no persisted work to resume; use loop-run.")
        elif loop["status"] != "waiting" or loop["execution"]["invocation_count"] != 0:
            raise ConflictError("Loop is not a newly created runnable loop.")

        self._authorize(actor, "loop.generate", loop_id, destination="local")
        self._ensure_existing_role_graph_nodes(loop_id)
        owner = str(uuid.uuid4())
        if not self._claim_execution(loop_id, owner, allow_existing=resume):
            return self.get_loop(loop_id, actor)

        processed = 0
        while True:
            state = self._execution_state(loop_id)
            if state["status"] != "running" or state["worker_id"] != owner:
                return self.get_loop(loop_id, actor)
            if invocation_limit is not None and processed >= invocation_limit:
                self._release_for_resume(loop_id, owner)
                return self.get_loop(loop_id, actor)
            pending = json.loads(state["pending_json"])
            if not pending:
                return self.get_loop(loop_id, actor)

            step = pending[0]
            evidence = self._evidence_for_loop(loop_id, actor, loop["goal"])
            inputs = self._role_inputs(loop_id, loop, step, evidence)
            try:
                prompt = build_role_prompt(step["role"], step["stage"], inputs)
            except ValidationError:
                self._fail_without_invocation(loop_id, owner, "invalid_role_input")
                raise

            invocation_index = state["invocation_count"] + 1
            if invocation_index > loop["max_rounds"]:
                self._mark_review_required(loop_id, owner, "invocation_budget_exhausted")
                return self.get_loop(loop_id, actor)
            execution_id = str(uuid.uuid5(uuid.UUID(loop_id), f"role-execution:{invocation_index}"))
            now = self._now()
            lease_expiry = self._lease_expiry()
            with self.database.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute(
                    "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
                ).fetchone()
                if current is None or current["status"] != "running" or current["worker_id"] != owner:
                    raise ConflictError("Loop execution ownership changed before role dispatch.")
                if current["current_role"] is not None:
                    raise ConflictError("A loop role invocation is already active.")
                connection.execute(
                    """INSERT INTO loop_rounds
                       (id,loop_id,round_index,stage,status,summary,output_json,job_id,created_at,updated_at,
                        role_name,input_json,attempt_count)
                       VALUES (?,?,?,?,'running','{}','{}',NULL,?,?,?,?,1)
                       ON CONFLICT(id) DO UPDATE SET status='running',summary='{}',output_json='{}',
                         created_at=excluded.created_at,updated_at=excluded.updated_at,
                         input_json=excluded.input_json,attempt_count=1,error_class=NULL
                       WHERE loop_rounds.status='queued'""",
                    (execution_id, loop_id, invocation_index, step["stage"], now, now,
                     step["role"], json.dumps(inputs, ensure_ascii=False, separators=(",", ":"))),
                )
                connection.execute(
                    """UPDATE loop_execution_state SET current_role=?,current_round=?,pending_json=?,
                       invocation_count=?,lease_expires_at=?,updated_at=? WHERE loop_id=? AND worker_id=?""",
                    (step["role"], invocation_index,
                     json.dumps(pending[1:], separators=(",", ":")), invocation_index,
                     lease_expiry, now, loop_id, owner),
                )
                connection.execute(
                    "UPDATE loop_roles SET status='running',updated_at=? WHERE loop_id=? AND role_name=?",
                    (now, loop_id, step["role"]),
                )

            try:
                self._controls_block()
            except PolicyDeniedError:
                self._defer_unstarted_role(loop_id, owner, execution_id, step, pending)
                return self.get_loop(loop_id, actor)
            try:
                generated = adapter.generate_text(prompt, response_schema=ROLE_SCHEMAS[step["role"]])
                if (not isinstance(generated, GenerationResult)
                        or generated.provider_id != adapter.provider_id
                        or generated.provider_id != "ollama"
                        or not isinstance(generated.model_id, str) or not generated.model_id.strip()):
                    raise ProviderError("Local provider returned invalid provenance.")
                parsed = parse_role_output(step["role"], generated.text,
                                           evidence_ids={item["id"] for item in evidence})
            except Exception as exc:
                error_class = exc.code if isinstance(exc, ProviderError) else (
                    "malformed_output" if isinstance(exc, ValidationError) else "role_execution_failed"
                )
                diagnostic = _safe_role_failure_detail(exc)
                cancelled = self._record_role_failure(loop_id, owner, execution_id, error_class, diagnostic)
                if cancelled:
                    return self.get_loop(loop_id, actor)
                raise ValidationError(f"AI Loop role invocation failed ({error_class}).") from exc

            completed = self._complete_role(
                loop_id, owner, execution_id, step, parsed, generated.provider_id, generated.model_id,
                evidence,
            )
            if not completed:
                return self.get_loop(loop_id, actor)
            self._ensure_role_graph_node(loop_id, execution_id, step, parsed,
                                         generated.provider_id, generated.model_id)
            processed += 1

            state = self._execution_state(loop_id)
            if state["status"] != "waiting":
                return self.get_loop(loop_id, actor)
            if invocation_limit is not None and processed >= invocation_limit:
                return self.get_loop(loop_id, actor)
            if not self._claim_execution(loop_id, owner, allow_existing=True):
                return self.get_loop(loop_id, actor)

    def _adapter_for(self, loop: dict, actor: Actor) -> InferenceAdapter:
        if loop["provider_mode"] != "ollama_api" or loop["cloud_opt_in"]:
            raise PolicyDeniedError("Hosted providers are not authorized for operations-room loop content.")
        if self.ollama is None:
            raise ValidationError("Local Ollama adapter is not configured.")
        self._authorize(actor, "loop.generate", loop["id"], destination="local")
        return self.ollama

    def _execution_state(self, loop_id: str) -> dict:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError("Loop execution state not found.")
        return dict(row)

    def _lease_expiry(self) -> str:
        return (self.clock().astimezone(timezone.utc) + timedelta(seconds=LEASE_SECONDS)) \
            .isoformat(timespec="seconds").replace("+00:00", "Z")

    def _claim_execution(self, loop_id: str, owner: str, *, allow_existing: bool) -> bool:
        now_dt = self.clock().astimezone(timezone.utc)
        now = self._now()
        expiry = (now_dt + timedelta(seconds=LEASE_SECONDS)).isoformat(timespec="seconds").replace("+00:00", "Z")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
            ).fetchone()
            if state is None:
                raise NotFoundError("Loop not found.")
            if state["status"] == "running":
                if state["lease_expires_at"] > now:
                    raise ConflictError("Another worker currently owns this loop.")
                if state["current_role"] is not None:
                    round_row = connection.execute(
                        "SELECT id FROM loop_rounds WHERE loop_id=? AND round_index=? AND status='running'",
                        (loop_id, state["current_round"]),
                    ).fetchone()
                    if round_row is not None:
                        connection.execute(
                            """UPDATE loop_rounds SET status='failed',summary=?,error_class=?,updated_at=?
                               WHERE id=? AND status='running'""",
                            ("The process stopped during an inference call; its result is unknown.",
                             "interrupted_unknown_result", now, round_row["id"]),
                        )
                    connection.execute(
                        """UPDATE loop_roles SET status='failed',updated_at=?
                           WHERE loop_id=? AND role_name=? AND status='running'""",
                        (now, loop_id, state["current_role"]),
                    )
                    connection.execute(
                        """UPDATE loop_execution_state SET status='review_required',current_role=NULL,
                           current_round=NULL,worker_id=NULL,lease_expires_at=NULL,
                           error_class='interrupted_unknown_result',updated_at=? WHERE loop_id=?""",
                        (now, loop_id),
                    )
                    connection.execute(
                        "UPDATE ai_loops SET status='failed',updated_at=? WHERE id=?", (now, loop_id)
                    )
                    return False
                connection.execute(
                    """UPDATE loop_execution_state SET status='waiting',worker_id=NULL,
                       lease_expires_at=NULL,updated_at=? WHERE loop_id=?""",
                    (now, loop_id),
                )
                state = connection.execute(
                    "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
                ).fetchone()
            if state["status"] != "waiting":
                if state["status"] in {"succeeded", "failed", "cancelled", "review_required"}:
                    return False
                raise ConflictError("Loop is not waiting for execution.")
            if state["invocation_count"] and not allow_existing:
                raise ConflictError("Loop has persisted invocations; use loop-resume.")
            connection.execute(
                """UPDATE loop_execution_state SET status='running',worker_id=?,lease_expires_at=?,
                   updated_at=? WHERE loop_id=? AND status='waiting'""",
                (owner, expiry, now, loop_id),
            )
            connection.execute(
                "UPDATE ai_loops SET status='debating',updated_at=? WHERE id=? AND status IN ('created','debating')",
                (now, loop_id),
            )
        return True

    def _defer_unstarted_role(self, loop_id: str, owner: str, execution_id: str,
                              step: dict, pending: list[dict]) -> None:
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
            ).fetchone()
            if state is None or state["status"] == "cancelled":
                connection.execute(
                    "UPDATE loop_rounds SET status='cancelled',updated_at=? WHERE id=? AND status='running'",
                    (now, execution_id),
                )
                return
            if state["status"] != "running" or state["worker_id"] != owner:
                return
            connection.execute(
                """UPDATE loop_rounds SET status='queued',attempt_count=0,error_class='dispatch_paused',
                   updated_at=? WHERE id=? AND status='running'""",
                (now, execution_id),
            )
            connection.execute(
                """UPDATE loop_execution_state SET status='waiting',current_role=NULL,current_round=NULL,
                   pending_json=?,invocation_count=MAX(0,invocation_count-1),worker_id=NULL,
                   lease_expires_at=NULL,updated_at=? WHERE loop_id=? AND worker_id=?""",
                (json.dumps(pending, separators=(",", ":")), now, loop_id, owner),
            )
            connection.execute(
                """UPDATE loop_roles SET status=CASE WHEN EXISTS(
                     SELECT 1 FROM loop_rounds WHERE loop_id=? AND role_name=? AND status='succeeded'
                   ) THEN 'succeeded' ELSE 'pending' END,updated_at=?
                   WHERE loop_id=? AND role_name=?""",
                (loop_id, step["role"], now, loop_id, step["role"]),
            )

    def _evidence_for_loop(self, loop_id: str, actor: Actor, query: str) -> list[dict]:
        rows = self.search_memory(loop_id, actor, query)
        return [{
            "id": row["id"],
            "display_name": row["display_name"],
            "trust_label": row["trust_label"],
            "content": row["content"],
            "provenance": "user_confirmed_import",
        } for row in rows]

    def _role_inputs(self, loop_id: str, loop: dict, step: dict, evidence: list[dict]) -> dict[str, Any]:
        outputs: dict[str, dict] = {}
        with self.database.connect() as connection:
            rows = connection.execute(
                """SELECT role_name,output_json FROM loop_rounds
                   WHERE loop_id=? AND status='succeeded' AND role_name IS NOT NULL
                   ORDER BY round_index""",
                (loop_id,),
            ).fetchall()
        for row in rows:
            outputs[row["role_name"]] = json.loads(row["output_json"])
        base = {
            "task": loop["goal"],
            "constraints": loop["constraints"],
            "evidence": evidence,
            "evidence_note": (
                "No grounded evidence has been ingested for this loop; model reasoning is not evidence."
                if not evidence else "Evidence is limited to these user-confirmed, loop-scoped records."
            ),
        }
        role = step["role"]
        stage = step["stage"]
        if role == "blue_team" and stage == "propose":
            return base
        if role == "red_team":
            return base | {"blue_team_proposal": outputs.get("blue_team")}
        if role == "judge":
            return base | {
                "blue_team_proposal": outputs.get("blue_team"),
                "red_team_critique": outputs.get("red_team"),
                "previous_judge_decision": outputs.get("judge") if stage == "revise" else None,
                "reviewer_findings": outputs.get("unbiased_reviewer") if stage == "revise" else None,
            }
        if role == "unbiased_reviewer":
            return base | {
                "blue_team_proposal": outputs.get("blue_team"),
                "red_team_critique": outputs.get("red_team"),
                "judge_decision": outputs.get("judge"),
                "previous_review": outputs.get("unbiased_reviewer") if stage == "re_audit" else None,
            }
        if role == "blue_team" and stage == "revise":
            return base | {
                "previous_proposal": outputs.get("blue_team"),
                "red_team_critique": outputs.get("red_team"),
                "judge_decision": outputs.get("judge"),
                "reviewer_findings": outputs.get("unbiased_reviewer"),
            }
        raise ValidationError("AI Loop role inputs are invalid.")

    def _complete_role(self, loop_id: str, owner: str, execution_id: str, step: dict,
                       output: dict, provider_id: str, model_id: str, evidence: list[dict]) -> bool:
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
            ).fetchone()
            if state is None or state["status"] == "cancelled":
                connection.execute(
                    "UPDATE loop_rounds SET status='cancelled',updated_at=? WHERE id=? AND status='running'",
                    (now, execution_id),
                )
                return False
            if (state["status"] != "running" or state["worker_id"] != owner
                    or state["current_role"] != step["role"]):
                return False
            updated = connection.execute(
                """UPDATE loop_rounds SET status='succeeded',summary=?,output_json=?,provider_id=?,model_id=?,
                   updated_at=? WHERE id=? AND status='running'""",
                (self._role_summary(step["role"], output), json.dumps(output, ensure_ascii=False, separators=(",", ":")),
                 provider_id, model_id, now, execution_id),
            )
            if not updated.rowcount:
                return False
            connection.execute(
                """UPDATE loop_roles SET status='succeeded',updated_at=?
                   WHERE loop_id=? AND role_name=?""",
                (now, loop_id, step["role"]),
            )
            pending = json.loads(state["pending_json"])
            verdict = output.get("verdict") if step["role"] == "unbiased_reviewer" else state["review_verdict"]
            status = "waiting"
            error_class = None
            if step["role"] == "unbiased_reviewer" and step["stage"] == "audit":
                if verdict == "pass":
                    status = "succeeded"
                elif verdict == "revise" and state["invocation_count"] + 2 <= connection.execute(
                        "SELECT max_rounds FROM ai_loops WHERE id=?", (loop_id,)
                    ).fetchone()["max_rounds"]:
                    pending = REVISION_STEPS[:2]
                else:
                    status = "review_required"
                    error_class = "reviewer_requested_revision" if verdict == "revise" else "reviewer_insufficient_evidence"
            elif step["role"] == "judge" and step["stage"] == "revise":
                max_rounds = connection.execute(
                    "SELECT max_rounds FROM ai_loops WHERE id=?", (loop_id,)
                ).fetchone()["max_rounds"]
                if verdict == "revise" and state["invocation_count"] < max_rounds:
                    pending = [REVISION_STEPS[2]]
                else:
                    status = "review_required"
                    error_class = "reviewer_budget_exhausted"
            elif step["role"] == "unbiased_reviewer" and step["stage"] == "re_audit":
                if verdict == "pass":
                    status = "succeeded"
                else:
                    status = "review_required"
                    error_class = "reviewer_requested_revision" if verdict == "revise" else "reviewer_insufficient_evidence"

            synthesis = None
            if status in {"succeeded", "review_required"}:
                history = connection.execute(
                    """SELECT role_name,output_json FROM loop_rounds
                       WHERE loop_id=? AND status='succeeded' AND role_name IS NOT NULL
                       ORDER BY round_index""",
                    (loop_id,),
                ).fetchall()
                latest = {row["role_name"]: json.loads(row["output_json"]) for row in history}
                synthesis = self._final_synthesis(latest, verdict, evidence)
                artifact_id = str(uuid.uuid5(uuid.UUID(loop_id), "artifact:final-synthesis"))
                connection.execute(
                    """INSERT OR IGNORE INTO loop_artifacts(id,loop_id,artifact_type,content,created_at)
                       VALUES(?,?,'final_synthesis',?,?)""",
                    (artifact_id, loop_id, synthesis, now),
                )
                connection.execute(
                    "UPDATE ai_loops SET status=?,updated_at=? WHERE id=?",
                    ("synthesized" if status == "succeeded" else "awaiting_user", now, loop_id),
                )
            connection.execute(
                """UPDATE loop_execution_state SET status=?,current_role=NULL,current_round=NULL,
                   pending_json=?,invocation_count=?,review_verdict=?,final_synthesis=COALESCE(?,final_synthesis),
                   error_class=?,worker_id=NULL,lease_expires_at=NULL,updated_at=? WHERE loop_id=?""",
                (status, json.dumps(pending, separators=(",", ":")), state["invocation_count"],
                 verdict, synthesis, error_class, now, loop_id),
            )
        return True

    def _role_summary(self, role_name: str, output: dict) -> str:
        primary = {
            "blue_team": "recommended_solution",
            "red_team": "counterarguments",
            "judge": "final_recommendation",
            "unbiased_reviewer": "verdict",
        }[role_name]
        value = output.get(primary)
        if isinstance(value, list):
            return "; ".join(value)[:1000]
        return str(value)[:1000]

    def _final_synthesis(self, outputs: dict[str, dict], verdict: str | None,
                         evidence: list[dict]) -> str:
        judge = outputs.get("judge")
        reviewer = outputs.get("unbiased_reviewer")
        if judge is None or reviewer is None:
            raise ValidationError("A final synthesis requires Judge and Reviewer outputs.")
        evidence_ids = {item["id"] for item in evidence}
        cited_ids = [item for item in judge["evidence_references"] if item in evidence_ids]
        evidence_gaps = list(judge["evidence_gaps"])
        if not evidence:
            evidence_gaps.append("No grounded evidence was ingested for this loop.")
        payload = {
            "final_recommendation": judge["final_recommendation"],
            "rationale": judge["rationale"],
            "accepted_arguments": judge["accepted_arguments"],
            "rejected_arguments": judge["rejected_arguments"],
            "revised_arguments": judge["revised_arguments"],
            "unresolved_objections": judge["unresolved_objections"],
            "confidence_limitations": judge["confidence_limitations"],
            "evidence_gaps": list(dict.fromkeys(evidence_gaps)),
            "evidence_references": cited_ids,
            "reviewer": reviewer,
            "review_verdict": verdict,
            "provenance": {
                "task_data": "user_provided",
                "model_generated_reasoning": True,
                "grounded_evidence": [
                    {"id": item["id"], "display_name": item["display_name"],
                     "trust_label": item["trust_label"], "provenance": item["provenance"]}
                    for item in evidence
                ],
                "evidence_status": "available" if evidence else "none_available",
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _record_role_failure(self, loop_id: str, owner: str, execution_id: str, error_class: str,
                             diagnostic: str | None = None) -> bool:
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = connection.execute(
                "SELECT * FROM loop_execution_state WHERE loop_id=?", (loop_id,)
            ).fetchone()
            if state is None or state["status"] == "cancelled":
                connection.execute(
                    "UPDATE loop_rounds SET status='cancelled',updated_at=? WHERE id=? AND status='running'",
                    (now, execution_id),
                )
                return True
            if state["status"] != "running" or state["worker_id"] != owner:
                return False
            connection.execute(
                """UPDATE loop_rounds SET status='failed',summary=?,error_class=?,updated_at=?
                   WHERE id=? AND status='running'""",
                (diagnostic or "Role invocation failed; provider output was not accepted.", error_class, now, execution_id),
            )
            connection.execute(
                """UPDATE loop_roles SET status='failed',updated_at=?
                   WHERE loop_id=? AND role_name=? AND status='running'""",
                (now, loop_id, state["current_role"]),
            )
            connection.execute(
                """UPDATE loop_execution_state SET status='failed',current_role=NULL,current_round=NULL,
                   error_class=?,worker_id=NULL,lease_expires_at=NULL,updated_at=? WHERE loop_id=?""",
                (error_class, now, loop_id),
            )
            connection.execute("UPDATE ai_loops SET status='failed',updated_at=? WHERE id=?", (now, loop_id))
        return False

    def _fail_without_invocation(self, loop_id: str, owner: str, error_class: str) -> None:
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE loop_execution_state SET status='failed',error_class=?,worker_id=NULL,
                   lease_expires_at=NULL,updated_at=? WHERE loop_id=? AND status='running' AND worker_id=?""",
                (error_class, now, loop_id, owner),
            )
            connection.execute("UPDATE ai_loops SET status='failed',updated_at=? WHERE id=?", (now, loop_id))

    def _mark_review_required(self, loop_id: str, owner: str, error_class: str) -> None:
        now = self._now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE loop_execution_state SET status='review_required',error_class=?,worker_id=NULL,
                   lease_expires_at=NULL,updated_at=? WHERE loop_id=? AND status='running' AND worker_id=?""",
                (error_class, now, loop_id, owner),
            )
            connection.execute("UPDATE ai_loops SET status='failed',updated_at=? WHERE id=?", (now, loop_id))

    def _ensure_role_graph_node(self, loop_id: str, execution_id: str, step: dict, output: dict,
                                provider_id: str, model_id: str) -> None:
        node_type = {
            "blue_team": "proposal",
            "red_team": "counterargument",
            "judge": "decision",
            "unbiased_reviewer": "claim",
        }[step["role"]]
        self.graph.add_node(
            loop_id, node_type, f"{ROLE_LABELS[step['role']]}: {step['stage']}",
            json.dumps(output, ensure_ascii=False, separators=(",", ":"))[:20_000],
            room_id="operations", sensitivity="internal",
            provenance={"provider": provider_id, "model": model_id, "execution_id": execution_id},
            node_id=str(uuid.uuid5(uuid.UUID(loop_id), f"role-node:{execution_id}")),
        )

    def _ensure_existing_role_graph_nodes(self, loop_id: str) -> None:
        with self.database.connect() as connection:
            rows = connection.execute(
                """SELECT id,role_name,stage,output_json,provider_id,model_id FROM loop_rounds
                   WHERE loop_id=? AND status='succeeded' AND role_name IS NOT NULL ORDER BY round_index""",
                (loop_id,),
            ).fetchall()
        for row in rows:
            step = {"role": row["role_name"], "stage": row["stage"]}
            self._ensure_role_graph_node(
                loop_id, row["id"], step, json.loads(row["output_json"]),
                row["provider_id"] or "unknown", row["model_id"] or "unknown",
            )

    def search_memory(self, loop_id: str, actor: Actor, query: str) -> list[dict]:
        self._authorize(actor, "loop.read", loop_id)
        self.get_loop(loop_id, actor)
        return self.graph.search_sources(loop_id, query, ingested_only=True)

    def graph_query(self, loop_id: str, actor: Actor, node_id: str | None = None) -> dict:
        self._authorize(actor, "loop.read", loop_id)
        self.get_loop(loop_id, actor)
        if node_id:
            return {"node": self.graph.get_node(loop_id, node_id), "edges": self.graph.neighbours(loop_id, node_id)}
        return {"nodes": self.graph.nodes(loop_id), "edges": [
            edge for node in self.graph.nodes(loop_id) for edge in self.graph.neighbours(loop_id, node["id"])
        ]}

    def artifacts(self, loop_id: str, actor: Actor) -> list[dict]:
        self.get_loop(loop_id, actor)
        with self.database.connect() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM loop_artifacts WHERE loop_id=? ORDER BY created_at", (loop_id,))]

    def compiled_prompt(self, loop_id: str, actor: Actor) -> dict:
        items = [item for item in self.artifacts(loop_id, actor) if item["artifact_type"] == "final_prompt"]
        if not items:
            raise NotFoundError("Compiled prompt not found.")
        return items[-1]

    def copy_prompt(self, loop_id: str, actor: Actor, clipboard) -> dict:
        prompt = self.compiled_prompt(loop_id, actor)
        result = clipboard.copy_clipboard(prompt["content"])
        if not result.ok:
            raise ValidationError(result.detail)
        return {"copied": True, "length": len(prompt["content"]), "handoff_url": self.handoff_url(loop_id, actor)}

    def handoff_url(self, loop_id: str, actor: Actor) -> str | None:
        loop = self.get_loop(loop_id, actor)
        return OFFICIAL_SITES.get(loop["provider_mode"])

    def handoff_status(self, loop_id: str, actor: Actor) -> dict | None:
        self.get_loop(loop_id, actor)
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM loop_handoffs WHERE loop_id=? ORDER BY created_at DESC",
                                     (loop_id,)).fetchone()
        return dict(row) if row else None

    def import_external(self, loop_id: str, actor: Actor, text: str, *, ingest: bool = False) -> dict:
        self._authorize(actor, "loop.ingest" if ingest else "loop.create", loop_id)
        if not isinstance(text, str) or not text.strip() or len(text) > 20000:
            raise ValidationError("Imported text is invalid.")
        loop = self.get_loop(loop_id, actor)
        handoff = self.handoff_status(loop_id, actor)
        if handoff is None or handoff["status"] != "awaiting_user":
            raise ConflictError("Loop is not awaiting an external response.")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE loop_handoffs SET imported_text=?,status='imported',updated_at=? WHERE id=?",
                               (text.strip(), self._now(), handoff["id"]))
            source_id = str(uuid.uuid4())
            connection.execute("INSERT INTO loop_sources VALUES (?,?,?,?,?,?,?)",
                               (source_id, loop_id, "user-imported-external", "user_provided_external",
                                text.strip(), 0, self._now()))
            connection.execute("UPDATE ai_loops SET status='imported',updated_at=? WHERE id=?", (self._now(), loop_id))
        node = self.graph.add_node(loop_id, "external_response", "Imported external response", text.strip()[:2000],
                                   room_id="operations", sensitivity="internal",
                                   provenance={"trust": "user_provided_external", "ingested": False})
        if ingest:
            return self.confirm_ingest(loop_id, actor, source_id, confirmed=True)
        return {"source_id": source_id, "node_id": node["id"], "ingested": False, "confirmation_required": True}

    def decline_handoff(self, loop_id: str, actor: Actor) -> dict:
        self._authorize(actor, "loop.create", loop_id)
        handoff = self.handoff_status(loop_id, actor)
        if handoff is None or handoff["status"] != "awaiting_user":
            raise ConflictError("Loop is not awaiting an external response.")
        with self.database.connect() as connection:
            connection.execute("UPDATE loop_handoffs SET status='declined',updated_at=? WHERE id=?",
                               (self._now(), handoff["id"]))
            connection.execute("UPDATE ai_loops SET status='declined',updated_at=? WHERE id=?", (self._now(), loop_id))
        return self.get_loop(loop_id, actor)

    def confirm_ingest(self, loop_id: str, actor: Actor, source_id: str, *, confirmed: bool) -> dict:
        self._authorize(actor, "loop.ingest", source_id)
        if not confirmed:
            raise PolicyDeniedError("External content is not ingested without confirmation.")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM loop_sources WHERE id=? AND loop_id=?",
                                     (source_id, loop_id)).fetchone()
            if row is None:
                raise NotFoundError("Source not found.")
            connection.execute("UPDATE loop_sources SET ingested=1 WHERE id=? AND loop_id=?", (source_id, loop_id))
        self.graph.add_node(loop_id, "source_summary", row["display_name"], row["content"][:2000],
                            room_id="operations", sensitivity="internal",
                            provenance={"source_id": source_id, "ingested": True})
        return {"source_id": source_id, "ingested": True}
