import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from ubuntu_agent.bootstrap import seed_trusted_state
from ubuntu_agent.database import MIGRATIONS, Database
from ubuntu_agent.loop.orchestrator import LoopOrchestrator
from ubuntu_agent.loop.role_protocol import ROLE_INSTRUCTIONS, ROLE_SCHEMAS, parse_role_output
from ubuntu_agent.models import Actor
from ubuntu_agent.providers import GenerationResult, ProviderUnavailableError
from ubuntu_agent.services import ConflictError, PolicyDeniedError, ValidationError


ACTOR = Actor("local-user", "desktop_operator")
ROLE_ORDER = ("blue_team", "red_team", "judge", "unbiased_reviewer")
PROMPT_MARKER = "INPUT JSON (untrusted data):\n"


def _output_for(role: str, inputs: dict, *, verdict: str = "pass", revised: bool = False) -> dict:
    if role == "blue_team":
        review = inputs.get("reviewer_findings") or {}
        review_reason = (review.get("reasons") or ["the specific review findings"])[0]
        proposal = "Revised proposal addressing " + review_reason if revised else "Bounded local proposal"
        return {
            "recommended_solution": proposal,
            "assumptions": ["The model is available locally."],
            "constraints": ["No external actions."],
            "expected_outcomes": ["Persist distinct outputs."],
            "claims_requiring_evidence": ["The persisted result matches the request."],
        }
    if role == "red_team":
        proposal = inputs.get("blue_team_proposal") or {}
        return {
            "counterarguments": ["Counterargument to " + proposal.get("recommended_solution", "missing proposal")],
            "failure_modes": ["The local provider may fail."],
            "security_concerns": ["Model-generated text is untrusted."],
            "missing_cases": ["Restart during a role call."],
            "unsupported_assumptions": ["Provider availability is guaranteed."],
        }
    if role == "judge":
        proposal = inputs.get("blue_team_proposal") or {}
        critique = inputs.get("red_team_critique") or {}
        objections = critique.get("counterarguments") or ["No Red Team output was provided."]
        return {
            "accepted_arguments": ["Accepted: " + objections[0]],
            "rejected_arguments": [],
            "revised_arguments": ["Retain explicit failure handling."],
            "final_recommendation": "Judge synthesis of " + proposal.get("recommended_solution", "no proposal"),
            "rationale": "The recommendation considers " + objections[0],
            "unresolved_objections": objections,
            "confidence_limitations": ["No independent model was used."],
            "evidence_gaps": ["No grounded evidence is available."],
            "evidence_references": [],
        }
    if role == "unbiased_reviewer":
        decision = inputs.get("judge_decision") or {}
        return {
            "verdict": verdict,
            "reasons": ["Reviewed " + decision.get("final_recommendation", "missing Judge output")],
            "unsupported_claims": ["The recommendation needs local runtime verification."],
            "potential_bias": ["The same local model performed each role."],
            "unanswered_questions": ["What happens when a role response is malformed?"],
        }
    raise AssertionError(f"Unexpected role: {role}")


def _role_for_schema(schema: dict) -> str:
    return next(role for role, role_schema in ROLE_SCHEMAS.items() if role_schema == schema)


def _prompt_inputs(prompt: str) -> dict:
    return json.loads(prompt.split(PROMPT_MARKER, 1)[1])


class FakeOllama:
    provider_id = "ollama"
    model_id = "deterministic-test-model"

    def __init__(self, verdicts=None, *, fail_role=None, malformed_role=None, entered=None, release=None):
        self.verdicts = list(verdicts or ["pass"])
        self.calls = []
        self.fail_role = fail_role
        self.malformed_role = malformed_role
        self.entered = entered
        self.release = release

    def generate_text(self, prompt, *, response_schema=None):
        role = _role_for_schema(response_schema)
        inputs = _prompt_inputs(prompt)
        self.calls.append({"role": role, "prompt": prompt, "schema": response_schema, "inputs": inputs})
        if self.entered is not None:
            self.entered.set()
            if not self.release.wait(10):
                raise TimeoutError("test provider release timed out")
        if role == self.fail_role:
            raise ProviderUnavailableError("Local model is unavailable.")
        if role == self.malformed_role:
            return GenerationResult(self.provider_id, self.model_id, '{"verdict": "pass"}')
        verdict = self.verdicts.pop(0) if role == "unbiased_reviewer" and self.verdicts else "pass"
        revised = role == "blue_team" and "reviewer_findings" in inputs
        response = _output_for(role, inputs, verdict=verdict, revised=revised)
        return GenerationResult(self.provider_id, self.model_id, json.dumps(response))


class AiLoopRoleTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.tempdir.name) / "loop.sqlite3")
        self.database.initialize()

    def tearDown(self):
        self.tempdir.cleanup()

    def create(self, *, max_rounds=4, fake=None):
        fake = fake or FakeOllama()
        orchestrator = LoopOrchestrator(self.database, ollama=fake)
        loop = orchestrator.create_loop(
            ACTOR, goal="Assess a local-first recovery design.",
            constraints=["Do not claim unverified execution."], max_rounds=max_rounds,
        )
        return orchestrator, fake, loop

    def test_four_roles_have_distinct_prompts_inputs_outputs_and_persisted_invocations(self):
        orchestrator, fake, loop = self.create()
        result = orchestrator.run_debate(loop["id"], ACTOR)

        self.assertEqual("succeeded", result["status"])
        self.assertEqual(list(ROLE_ORDER), [call["role"] for call in fake.calls])
        self.assertEqual(4, len({call["prompt"] for call in fake.calls}))
        self.assertEqual(4, len({call["schema"] and json.dumps(call["schema"], sort_keys=True)
                                 for call in fake.calls}))
        for role in ROLE_ORDER:
            instruction = ROLE_INSTRUCTIONS[(role, {
                "blue_team": "propose", "red_team": "challenge",
                "judge": "synthesize", "unbiased_reviewer": "audit",
            }[role])]
            self.assertIn(instruction, next(call["prompt"] for call in fake.calls if call["role"] == role))

        by_role = {call["role"]: call for call in fake.calls}
        proposal = _output_for("blue_team", by_role["blue_team"]["inputs"])
        self.assertEqual(proposal, by_role["red_team"]["inputs"]["blue_team_proposal"])
        self.assertEqual(proposal, by_role["judge"]["inputs"]["blue_team_proposal"])
        self.assertEqual(
            by_role["red_team"]["inputs"]["blue_team_proposal"],
            by_role["judge"]["inputs"]["blue_team_proposal"],
        )
        self.assertIsNotNone(by_role["judge"]["inputs"]["red_team_critique"])
        self.assertEqual(
            _output_for("judge", by_role["judge"]["inputs"]),
            by_role["unbiased_reviewer"]["inputs"]["judge_decision"],
        )

        rounds = result["rounds"]
        self.assertEqual(ROLE_ORDER, tuple(row["role_name"] for row in rounds))
        self.assertEqual(4, len({row["id"] for row in rounds}))
        self.assertTrue(all(row["loop_id"] == loop["id"] for row in rounds))
        self.assertTrue(all(row["status"] == "succeeded" for row in rounds))
        self.assertTrue(all(row["attempt_count"] == 1 for row in rounds))
        self.assertTrue(all(row["provider_id"] == "ollama" for row in rounds))
        self.assertTrue(all(row["model_id"] == fake.model_id for row in rounds))
        self.assertTrue(all(role["status"] == "succeeded" and len(role["executions"]) == 1
                            for role in result["roles"]))

        final = json.loads(result["execution"]["final_synthesis"])
        judge = json.loads(rounds[2]["output_json"])
        self.assertEqual(judge["final_recommendation"], final["final_recommendation"])
        self.assertIn(judge["accepted_arguments"][0], final["accepted_arguments"])
        self.assertEqual("none_available", final["provenance"]["evidence_status"])
        self.assertEqual([], final["evidence_references"])
        self.assertIn("No grounded evidence", final["evidence_gaps"][0])

    def test_judge_rejects_gemma_na_citation_sentinel_without_grounded_evidence(self):
        # Captured Gemma JSON shape from the live failing Judge invocation.
        output = _output_for("judge", {"blue_team_proposal": {"recommended_solution": "A proposal."},
                                       "red_team_critique": {"counterarguments": []}})
        output["evidence_references"] = ["N/A"]
        parsed = parse_role_output("judge", json.dumps(output), evidence_ids=set())
        self.assertEqual([], parsed["evidence_references"])

    def test_judge_still_rejects_unknown_citations_when_evidence_exists(self):
        output = _output_for("judge", {"blue_team_proposal": {"recommended_solution": "A proposal."},
                                       "red_team_critique": {"counterarguments": []}})
        output["evidence_references"] = ["N/A"]
        with self.assertRaises(ValidationError):
            parse_role_output("judge", json.dumps(output), evidence_ids={"real-evidence-id"})

    def test_reviewer_verdict_controls_terminal_state_and_never_false_approves(self):
        for verdict, expected in (
            ("pass", "succeeded"),
            ("revise", "review_required"),
            ("insufficient_evidence", "review_required"),
        ):
            with self.subTest(verdict=verdict):
                fake = FakeOllama(verdicts=[verdict])
                orchestrator, _, loop = self.create(fake=fake)
                result = orchestrator.run_debate(loop["id"], ACTOR)
                self.assertEqual(expected, result["status"])
                self.assertEqual(verdict, result["execution"]["review_verdict"])
                self.assertEqual(4, result["execution"]["invocation_count"])
                self.assertEqual(4, len(fake.calls))

    def test_revision_uses_review_findings_and_is_bounded_to_one_cycle(self):
        fake = FakeOllama(verdicts=["revise", "pass"])
        orchestrator, _, loop = self.create(max_rounds=7, fake=fake)
        result = orchestrator.run_debate(loop["id"], ACTOR)

        self.assertEqual("succeeded", result["status"])
        self.assertEqual(7, result["execution"]["invocation_count"])
        self.assertEqual(
            ["blue_team", "red_team", "judge", "unbiased_reviewer",
             "blue_team", "judge", "unbiased_reviewer"],
            [call["role"] for call in fake.calls],
        )
        first_review = _output_for("unbiased_reviewer", fake.calls[3]["inputs"], verdict="revise")
        self.assertEqual(first_review["reasons"], fake.calls[4]["inputs"]["reviewer_findings"]["reasons"])
        self.assertIn("reviewer_findings", fake.calls[5]["inputs"])
        self.assertEqual(
            _output_for("judge", fake.calls[5]["inputs"]),
            fake.calls[6]["inputs"]["judge_decision"],
        )
        self.assertEqual("pass", result["execution"]["review_verdict"])
        self.assertEqual(7, len(result["rounds"]))

    def test_budget_exhaustion_does_not_rerun_reviewer_or_approve(self):
        fake = FakeOllama(verdicts=["revise"])
        orchestrator, _, loop = self.create(max_rounds=6, fake=fake)
        result = orchestrator.run_debate(loop["id"], ACTOR)

        self.assertEqual("review_required", result["status"])
        self.assertEqual("awaiting_user", result["legacy_status"])
        self.assertEqual(6, result["execution"]["invocation_count"])
        self.assertEqual(["blue_team", "red_team", "judge", "unbiased_reviewer",
                          "blue_team", "judge"], [call["role"] for call in fake.calls])
        self.assertEqual("revise", result["execution"]["review_verdict"])
        self.assertEqual(1, sum(row["role_name"] == "unbiased_reviewer" for row in result["rounds"]))

    def test_provider_failure_and_malformed_output_are_persisted_as_failures(self):
        for fake, error_class in (
            (FakeOllama(fail_role="red_team"), "PROVIDER_UNAVAILABLE"),
            (FakeOllama(malformed_role="blue_team"), "malformed_output"),
            (FakeOllama(malformed_role="unbiased_reviewer"), "malformed_output"),
        ):
            with self.subTest(error_class=error_class):
                orchestrator, _, loop = self.create(fake=fake)
                with self.assertRaises(ValidationError):
                    orchestrator.run_debate(loop["id"], ACTOR)
                result = orchestrator.get_loop(loop["id"], ACTOR)
                self.assertEqual("failed", result["status"])
                failed = [row for row in result["rounds"] if row["status"] == "failed"]
                self.assertEqual(1, len(failed))
                self.assertEqual(error_class, failed[0]["error_class"])
                self.assertIsNone(result["execution"]["final_synthesis"])

    def test_late_provider_response_cannot_overwrite_cancellation(self):
        orchestrator = LoopOrchestrator(self.database)
        state = {}

        class CancellingProvider(FakeOllama):
            def generate_text(self, prompt, *, response_schema=None):
                result = super().generate_text(prompt, response_schema=response_schema)
                orchestrator.cancel(state["loop_id"], ACTOR)
                return result

        fake = CancellingProvider()
        orchestrator.ollama = fake
        loop = orchestrator.create_loop(ACTOR, goal="Check cancellation after model response.", max_rounds=4)
        state["loop_id"] = loop["id"]
        result = orchestrator.run_debate(loop["id"], ACTOR)
        self.assertEqual("cancelled", result["status"])
        self.assertEqual(["cancelled"], [row["status"] for row in result["rounds"]])
        self.assertEqual(0, sum(row["status"] == "succeeded" for row in result["rounds"]))
        self.assertIsNone(result["execution"]["final_synthesis"])

    def test_completed_invocations_are_skipped_after_service_restart(self):
        first = FakeOllama()
        orchestrator = LoopOrchestrator(self.database, ollama=first)
        loop = orchestrator.create_loop(ACTOR, goal="Resume from an invocation checkpoint.", max_rounds=4)
        partial = orchestrator.run_debate(loop["id"], ACTOR, invocation_limit=2)
        self.assertEqual("waiting", partial["status"])
        self.assertEqual(2, partial["execution"]["invocation_count"])
        completed_before = [(row["id"], row["output_json"]) for row in partial["rounds"]]

        reopened = Database(Path(self.tempdir.name) / "loop.sqlite3")
        second = FakeOllama()
        resumed = LoopOrchestrator(reopened, ollama=second).resume_loop(loop["id"], ACTOR)
        self.assertEqual("succeeded", resumed["status"])
        self.assertEqual(["judge", "unbiased_reviewer"], [call["role"] for call in second.calls])
        self.assertEqual(4, resumed["execution"]["invocation_count"])
        self.assertEqual(completed_before, [(row["id"], row["output_json"]) for row in resumed["rounds"][:2]])
        self.assertEqual(4, len({row["id"] for row in resumed["rounds"]}))

    def test_persisted_checkpoint_resumes_in_a_new_python_process(self):
        database_path = str(Path(self.tempdir.name) / "process-restart.sqlite3")
        script = """
import json, sys
from ubuntu_agent.database import Database
from ubuntu_agent.loop.orchestrator import LoopOrchestrator
from ubuntu_agent.loop.role_protocol import ROLE_SCHEMAS
from ubuntu_agent.models import Actor
from ubuntu_agent.providers import GenerationResult

def payload(role):
    if role == "blue_team":
        return {"recommended_solution":"Local proposal","assumptions":[],"constraints":[],
                "expected_outcomes":[],"claims_requiring_evidence":[]}
    if role == "red_team":
        return {"counterarguments":["A concrete objection"],"failure_modes":[],"security_concerns":[],
                "missing_cases":[],"unsupported_assumptions":[]}
    if role == "judge":
        return {"accepted_arguments":["A concrete objection"],"rejected_arguments":[],
                "revised_arguments":[],"final_recommendation":"Judge recommendation","rationale":"Compared inputs",
                "unresolved_objections":[],"confidence_limitations":[],"evidence_gaps":["No evidence"],
                "evidence_references":[]}
    return {"verdict":"pass","reasons":["Reviewed the decision"],"unsupported_claims":[],
            "potential_bias":[],"unanswered_questions":[]}

class Fake:
    provider_id="ollama"
    model_id="process-restart-test"
    def generate_text(self, prompt, *, response_schema=None):
        role=next(role for role, schema in ROLE_SCHEMAS.items() if schema == response_schema)
        return GenerationResult(self.provider_id,self.model_id,json.dumps(payload(role)))

db=Database(sys.argv[1]); db.initialize()
actor=Actor("local-user","desktop_operator")
runner=LoopOrchestrator(db,ollama=Fake())
if sys.argv[2] == "start":
    loop=runner.create_loop(actor,goal="Resume after a process boundary.",max_rounds=4)
    result=runner.run_debate(loop["id"],actor,invocation_limit=2)
else:
    result=runner.resume_loop(sys.argv[3],actor)
print(json.dumps({"id":result["id"],"status":result["status"],
                  "invocation_count":result["execution"]["invocation_count"]}))
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [
            str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH"),
        ]))
        started = subprocess.run(
            [sys.executable, "-c", script, database_path, "start"],
            check=True, capture_output=True, text=True, timeout=30, env=env,
        )
        first_state = json.loads(started.stdout)
        self.assertEqual("waiting", first_state["status"])
        resumed = subprocess.run(
            [sys.executable, "-c", script, database_path, "resume", first_state["id"]],
            check=True, capture_output=True, text=True, timeout=30, env=env,
        )
        final_state = json.loads(resumed.stdout)
        self.assertEqual("succeeded", final_state["status"])
        self.assertEqual(4, final_state["invocation_count"])
        with Database(database_path).connect() as connection:
            records = connection.execute(
                "SELECT role_name,status,provider_id,model_id FROM loop_rounds WHERE loop_id=? ORDER BY round_index",
                (first_state["id"],),
            ).fetchall()
            self.assertEqual(list(ROLE_ORDER), [row["role_name"] for row in records])
            self.assertTrue(all(row["status"] == "succeeded" for row in records))
            self.assertTrue(all(row["provider_id"] == "ollama" for row in records))
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])

    def test_concurrent_workers_cannot_claim_the_same_active_role(self):
        entered, release = threading.Event(), threading.Event()
        fake = FakeOllama(entered=entered, release=release)
        orchestrator = LoopOrchestrator(self.database, ollama=fake)
        loop = orchestrator.create_loop(ACTOR, goal="Ensure the loop has one active owner.", max_rounds=4)
        runner = threading.Thread(
            target=lambda: orchestrator.run_debate(loop["id"], ACTOR),
            daemon=True,
        )
        runner.start()
        self.assertTrue(entered.wait(5))
        competing = LoopOrchestrator(self.database, ollama=FakeOllama())
        with self.assertRaises(ConflictError):
            competing.resume_loop(loop["id"], ACTOR)
        release.set()
        runner.join(10)
        self.assertFalse(runner.is_alive())
        self.assertEqual("succeeded", orchestrator.get_loop(loop["id"], ACTOR)["status"])
        self.assertEqual(4, len(fake.calls))

    def test_expired_inflight_invocation_requires_review_instead_of_repeating(self):
        orchestrator, _, loop = self.create()
        now = "2020-01-01T00:00:00Z"
        execution_id = "expired-execution"
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO loop_rounds
                   (id,loop_id,round_index,stage,status,summary,output_json,job_id,created_at,updated_at,
                    role_name,input_json,attempt_count)
                   VALUES(?,?,1,'propose','running','{}','{}',NULL,?,?, 'blue_team','{}',1)""",
                (execution_id, loop["id"], now, now),
            )
            connection.execute(
                """UPDATE loop_execution_state SET status='running',current_role='blue_team',
                   current_round=1,invocation_count=1,worker_id='dead-process',
                   lease_expires_at=? WHERE loop_id=?""",
                (now, loop["id"]),
            )
        recovered = orchestrator.resume_loop(loop["id"], ACTOR)
        self.assertEqual("review_required", recovered["status"])
        self.assertEqual("interrupted_unknown_result", recovered["execution"]["error_class"])
        self.assertEqual(["failed"], [row["status"] for row in recovered["rounds"]])
        self.assertEqual([], _.calls)

    def test_cloud_provider_is_rejected_for_operations_room_loop_data(self):
        with self.assertRaises(PolicyDeniedError):
            LoopOrchestrator(self.database, ollama=FakeOllama()).create_loop(
                ACTOR, goal="Private task data", provider_mode="gemini_api", cloud_opt_in=True,
            )
        self.assertEqual("ok", self.database.integrity_check())

    def test_budget_validation_and_foreign_key_integrity(self):
        orchestrator = LoopOrchestrator(self.database, ollama=FakeOllama())
        with self.assertRaises(ValidationError):
            orchestrator.create_loop(ACTOR, goal="Too few calls", max_rounds=3)
        loop = orchestrator.create_loop(ACTOR, goal="Integrity check")
        with self.database.connect() as connection:
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            self.assertEqual([], violations)
            self.assertEqual(1, connection.execute(
                "SELECT COUNT(*) FROM loop_execution_state WHERE loop_id=?", (loop["id"],)
            ).fetchone()[0])

    def test_version_six_database_keeps_history_and_marks_legacy_output_unverified(self):
        legacy = Database(Path(self.tempdir.name) / "legacy-v6.sqlite3")
        timestamp = "2026-10-11T00:00:00Z"
        with legacy.connect() as connection:
            connection.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            for version, migration in MIGRATIONS:
                if version > 6:
                    break
                Database._execute_statements(connection, migration)
                connection.execute("INSERT INTO schema_migrations VALUES (?,?)", (version, timestamp))
            seed_trusted_state(connection)
            connection.execute(
                "INSERT INTO ai_loops VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("legacy-v6-loop", "operations", "desktop_operator", "Legacy prompt", "[]",
                 "ollama_api", 0, "synthesized", 4, None, timestamp, timestamp, None),
            )
            connection.execute(
                "INSERT INTO loop_roles VALUES (?,?,?,?,?,?,?)",
                ("legacy-role", "legacy-v6-loop", "blue_team", "Blue Team", "complete", timestamp, timestamp),
            )
            connection.execute(
                """INSERT INTO loop_rounds(id,loop_id,round_index,stage,status,summary,output_json,
                   job_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("legacy-round", "legacy-v6-loop", 1, "proposal", "succeeded", "Old result",
                 '{"summary":"old"}', None, timestamp, timestamp),
            )
        legacy.initialize()
        with legacy.connect() as connection:
            loop = connection.execute("SELECT goal FROM ai_loops WHERE id='legacy-v6-loop'").fetchone()
            round_row = connection.execute("SELECT summary,output_json FROM loop_rounds WHERE id='legacy-round'").fetchone()
            role = connection.execute("SELECT status FROM loop_roles WHERE id='legacy-role'").fetchone()
            state = connection.execute(
                "SELECT status,error_class FROM loop_execution_state WHERE loop_id='legacy-v6-loop'"
            ).fetchone()
            version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
        self.assertEqual("Legacy prompt", loop["goal"])
        self.assertEqual(("Old result", '{"summary":"old"}'), tuple(round_row))
        self.assertEqual("succeeded", role["status"])
        self.assertEqual(("review_required", "legacy_execution_not_resumable"), tuple(state))
        self.assertEqual(max(version for version, _ in MIGRATIONS), version)

    @unittest.skipUnless(
        os.environ.get("UBUNTU_AGENT_RUN_LOCAL_LOOP_INTEGRATION") == "1",
        "set UBUNTU_AGENT_RUN_LOCAL_LOOP_INTEGRATION=1 to run local Gemma integration",
    )
    def test_opt_in_local_gemma_loop_persists_all_four_real_roles(self):
        try:
            with urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as response:
                models = json.load(response).get("models", [])
        except (OSError, URLError):
            self.skipTest("Ollama is not reachable on the local endpoint.")
        configured_model = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-it-q4_K_M")
        if not any(item.get("name") == configured_model for item in models):
            self.skipTest(f"Configured local model {configured_model!r} is not installed.")

        database_path = str(Path(self.tempdir.name) / "real-gemma.sqlite3")
        script = """
import json, sys
from ubuntu_agent.database import Database
from ubuntu_agent.loop.orchestrator import LoopOrchestrator
from ubuntu_agent.models import Actor
from ubuntu_agent.provider_config import ProviderConfig
from ubuntu_agent.providers import OllamaProvider

db=Database(sys.argv[1]); db.initialize()
config=ProviderConfig.from_environment()
actor=Actor("local-user","desktop_operator")
runner=LoopOrchestrator(db,ollama=OllamaProvider(config))
loop=runner.create_loop(actor,goal="Describe a safe way to resume a local SQLite workflow after a process restart.",
                        constraints=["Use no external sources or tools.","State uncertainty honestly."],
                        max_rounds=4)
result=runner.run_debate(loop["id"],actor)
print(json.dumps({"id":result["id"],"status":result["status"],
                  "execution":result["execution"]}))
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [
            str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH"),
        ]))
        env["OLLAMA_TIMEOUT_SECONDS"] = "90"
        completed = subprocess.run(
            [sys.executable, "-c", script, database_path],
            check=True, capture_output=True, text=True, timeout=390, env=env,
        )
        run = json.loads(completed.stdout)
        self.assertIn(run["status"], {"succeeded", "review_required"})
        with Database(database_path).connect() as connection:
            rounds = connection.execute(
                """SELECT role_name,status,provider_id,model_id,output_json FROM loop_rounds
                   WHERE loop_id=? ORDER BY round_index""",
                (run["id"],),
            ).fetchall()
            self.assertEqual(4, len(rounds))
            self.assertEqual(ROLE_ORDER, tuple(row["role_name"] for row in rounds))
            self.assertTrue(all(row["status"] == "succeeded" for row in rounds))
            self.assertTrue(all(row["provider_id"] == "ollama" for row in rounds))
            self.assertTrue(all(row["model_id"] == configured_model for row in rounds))
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
            artifacts = connection.execute(
                """SELECT content FROM loop_artifacts
                   WHERE loop_id=? AND artifact_type='final_synthesis'""",
                (run["id"],),
            ).fetchall()
            self.assertEqual(1, len(artifacts))
        persisted_synthesis = json.loads(artifacts[0]["content"])
        self.assertEqual(run["execution"]["review_verdict"], persisted_synthesis["review_verdict"])
        self.assertEqual([], persisted_synthesis["evidence_references"])
        self.assertEqual("none_available", persisted_synthesis["provenance"]["evidence_status"])


if __name__ == "__main__":
    unittest.main()
