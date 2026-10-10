# Autonomy and Access Policy Matrix

## Purpose

This document is the canonical default permission matrix for rooms, personas and actions. The enforcement procedure is defined in `04_SECURITY_PIPELINE.md`. The UI must reflect these rules but cannot enforce them by hiding controls.

All permissions are deny-by-default. A persona is a task mode, not a security boundary. The authenticated user can configure selected grants, but an agent/persona cannot grant itself new access or alter the policy that constrains it.

## Knowledge rooms

| Room | Typical content | Default cloud policy |
|---|---|---|
| `public_research` | Public sources, web extracts, non-sensitive references | May be sent to an enabled provider subject to task scope |
| `academic` | Courses, assignments, notes, exam preparation | Local by default; only selected content may be disclosed under an explicit allowed policy |
| `projects` | Repositories, code, technical decisions, project notes | Local by default; allow only selected non-sensitive excerpts if enabled |
| `opportunities` | Internships, scholarships, competitions and leads | Selected public/non-sensitive data may be sent when required |
| `operations` | Tasks, deadlines, reminder state, job status | Minimum fields only; do not include unrelated task history |
| `personal_vault` | Personal notes, identity, routines and private records | Local-only by default |
| `health` | Health/medical records and related notes | Local-only; no cloud forwarding by default |

Room labels are a sensitivity and retrieval boundary. They are not merely UI categories. Authorization must be enforced before returning content or graph metadata.

## Personas and default access

Legend: `R` = read in assigned scope; `W` = create/update via approved domain service; `P` = prepare proposal only; `A` = requires action-specific approval; `—` = denied by default.

| Persona | Operations | Academic | Projects | Public Research | Opportunities | Personal Vault | Health |
|---|---|---|---|---|---|---|---|
| Task & Deadline Manager | R/W | R for task-linked fields | R for task-linked fields | R | R for lead-linked fields | — | — |
| Exam & Study Coach | R for deadlines | R/W for study tasks and approved notes | — | R | — | — | — |
| AI/ML Researcher | R for job state | — unless explicitly bridged | R in assigned project | R | R when relevant to assigned task | — | — |
| Desktop Operator | R for active job/approval | only data explicitly attached to current task | only data explicitly attached to current task | R | only data explicitly attached to current task | — | — |

These are default capabilities, not grants to every record in a room. The policy engine narrows them by task scope, ownership, sensitivity, file/domain allowlists and user grants. Future personas (Robotics, Quantum, Hackathon Strategist, Opportunity Scout, Personal Assistant) must get explicit profiles before activation.

## Action matrix

| Action | Default autonomy | Required control |
|---|---|---|
| Read an authorized task, document or website | Allowed within scope | Check room/resource and domain permissions |
| Search memory | Allowed within permitted rooms | Apply access filter before vector/graph retrieval |
| Create a task or reminder | Allowed after typed validation | Clarify ambiguous deadlines before scheduling |
| Change a Kanban state | Allowed for routine tasks | Persist event; undo on failure; completion requires evidence |
| Draft an email, message, command or report | Allowed | Keep draft local unless disclosure is permitted |
| Read files in approved workspace | Allowed | Canonicalize path; prevent traversal/symlink escape |
| Create or edit workspace files | Conditional | Registered operation; scoped path; checkpoint/diff; policy grant |
| Delete files or overwrite important data | Approval required | Exact target preview; backup/checkpoint where possible |
| Send a message, publish or submit coursework | Fresh approval required | Exact recipient/destination/content/file; verify outcome |
| Install packages or alter system configuration | Approval required; privileged operations use separate tier | Show package/source/command and expected system changes |
| Use `sudo`, change permissions/security, access credentials | Denied to generic model shell | Narrow privileged helper plus separate elevated approval; some actions remain denied |
| Send context to hosted model | Only if explicit provider/data policy allows | Pre-send room/sensitivity check and minimum-context disclosure |
| Change RBAC, room policy or provider policy | User/admin action only | Re-authenticate where feasible; confirmation and audit |

## Cross-room bridges

A bridge is a narrow, explicit projection of approved fields. Example: a project room may share `project_id`, `assignment_title` and `deadline` with Operations, while keeping project notes and source documents private.

Every bridge must define:

- source room and source entity/field allowlist
- destination room and receiving service/persona
- purpose and expiry or review condition
- creator, creation time, policy reference and revocation status
- whether downstream cloud processing is allowed for the bridged fields

Bridges are visible, purpose-limited, revocable and deny-by-default. They are not hidden backdoors and never imply access to the entire source graph. Revocation must prevent future reads and trigger invalidation of derived indexes/caches where feasible. Preserve only minimal audit metadata required to show that the bridge existed.

## Approval and autonomy rules

- Approval is bound to one exact action, target and normalized argument set.
- Changes to file, destination, recipient, command, course, assignment or data disclosure require a new approval.
- A parent task being approved does not approve all child operations.
- Sleeping user, overnight execution or repeated retries never count as approval.
- High-risk actions require a fresh approval immediately before execution.
- The policy engine must fail closed if identity, scope or risk cannot be determined.
- A model may request an expanded scope but cannot grant it.
- A user-approved task still obeys hard deny rules and provider/service restrictions.

## Policy evaluation inputs

Every tool call should be evaluated against: actor/user, persona, room, resource ID, action/tool ID, sensitivity label, provider destination, current job scope, risk tier, applicable approval, budget, time limits and current system mode (`normal`, `paused`, `maintenance`).

Return a structured decision: `allow`, `deny` or `requires_approval`, with policy ID, human-readable reason, sanitized target, and decision timestamp. The executor must re-check the decision immediately before running a side effect.

## Example decisions

- Task Manager creates a reminder for an assignment with a confirmed date: `allow`.
- Researcher searches the Public Research room and stores citations: `allow`.
- Desktop Operator reads Health-room notes without a grant: `deny`.
- Researcher asks a cloud provider to analyze a private repository when cloud disclosure is disabled: `deny`.
- Agent prepares a Classroom submission preview: `allow` if the course/file are in scope.
- Agent clicks final Turn in without fresh approval: `deny`.
- Agent requests arbitrary `sudo rm -rf ...`: `deny`; generic root-shell access does not exist.
