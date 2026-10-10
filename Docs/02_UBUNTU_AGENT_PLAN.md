# Ubuntu Agent — Student Productivity OS
## Product Specification and Implementation Plan

**Document type:** Product + engineering plan  
**Status:** Prototype specification  
**Primary platform:** Ubuntu Linux  
**Primary interaction:** Terminal-first agent with a lightweight local dashboard  
**Core promise:** Give the agent an outcome, then receive useful work, reminders, and evidence without having to coordinate every AI step manually.

---

# 1. Executive Overview

Ubuntu Agent is a local-first personal productivity operator for students and technical builders. It combines an AI agent, a personal task tracker, deadline and reminder management, compartmentalized memory, multi-model research workflows, controlled desktop automation, and auditable execution.

The product is not intended to be another chat window or another task board that the user must constantly maintain. Its central interaction is outcome-oriented: the user states an intention in ordinary language, and the agent converts it into structured tasks, dates, files, dependencies, reminders, and a bounded workflow.

Example:

> “I have the Unit 2 assignment for Data Structures due on the 7th. The report is `ds_unit2.pdf`. Remind me to finish it two days before, check it the evening before, and help me submit it to the correct Google Classroom course.”

The agent should:

1. Resolve which month and year the 7th refers to; ask if the date is ambiguous rather than silently guessing.
2. Create an assignment card linked to the correct subject/course, due date, expected file, and submission destination.
3. Add the card to the right Kanban lane and category.
4. Create reminder events from the requested schedule and the user's configured defaults.
5. Track file readiness and whether the work is drafted, reviewed, ready to submit, or submitted.
6. Inspect the file and identify the correct course/assignment in the connected Classroom workflow.
7. Prepare the submission and show the exact course, assignment, and file to be uploaded.
8. Require explicit approval before the external side effect of submitting coursework.
9. Verify the result and record the submission timestamp and evidence where the available interface makes that possible.
10. Notify the user only when a meaningful milestone, decision, blocker, or deadline needs attention.

**Product thesis:** reduce cognitive load through bounded autonomy. The agent should do the coordination, organization, research, and reversible preparation itself. It must retain clear user control over sensitive data, privileged system operations, and external or irreversible actions.

## Product goals

- Capture tasks and ideas with minimal friction, including natural-language input.
- Maintain one reliable source of truth for deadlines, reminders, status, files, and dependencies.
- Make work visible through an inbox, Kanban board, category sidebar, calendar/deadline views, and concise notifications.
- Keep separate, permissioned knowledge rooms and purpose-specific personas.
- Execute multi-step research and development jobs with checkpoints and an auditable report.
- Use local Gemma for appropriate work and route to hosted reasoning only when policy permits.
- Operate approved websites and desktop applications using the least brittle available interaction method.
- Make actions inspectable, stoppable, recoverable, and appropriately gated.

## Non-goals for the first prototype

- Unrestricted autonomous root access or arbitrary shell execution.
- Guaranteed operation of every website or desktop application.
- Fully autonomous submission of coursework, sending messages, deleting important files, purchasing items, or changing system security.
- Building a large multi-agent framework before a reliable single-agent execution loop exists.
- Treating a language-model vote as proof that a claim is true.
- Sending every memory or desktop screenshot to a cloud model.

---

# 2. Product Feature Overview

## 2.1 Personal productivity tracker

### Inbox

A low-friction landing area for unprocessed tasks, ideas, sticky notes, links, files, reminders, and things captured from conversations. The user should be able to type or dictate an item without immediately deciding every field.

Inbox actions:

- Capture a plain note or task.
- Paste a URL or file path and attach it to an item.
- Ask the agent to categorize, summarize, split, or schedule an item.
- Convert a note into a task, project, assignment, event, or research lead.
- Keep an item in the inbox until reviewed; do not silently discard it.

### Kanban board

Default lanes:

- **Inbox** — captured but not triaged.
- **Next** — planned and actionable.
- **In Progress** — active work.
- **Waiting** — blocked on a person, reply, access, or external dependency.
- **Review** — work produced and awaiting verification.
- **Ready to Submit** — deliverable is prepared, but the final external action has not happened.
- **Done** — complete and verified.
- **Archived** — retained for reference, removed from active views.

Users can configure lanes. Moving a card should persist immediately and be recorded in activity history. The agent may suggest a lane change; it should not silently mark work complete without a completion signal or verification rule.

### Sticky-note categories and sidebar

Use a simple, configurable category sidebar rather than a wall of tags. Suggested categories:

- Academics
- Projects
- Hackathons & Competitions
- AI/ML Research
- Robotics
- Quantum Computing
- Opportunities
- Personal / Admin
- Waiting / Follow-up

A note may have one primary category and optional labels. Keep labels limited and useful. Category answers “what area is this in?”; a project answers “which larger body of work does it belong to?”; status answers “what state is it in?” These should not be conflated.

### Task and assignment cards

Minimum fields:

- Title and description
- Item type: task, assignment, exam, event, idea, follow-up, research job, or reminder
- Status and priority
- Category, project, and responsible persona
- Due date/time and timezone
- Estimated duration and optional work sessions
- Reminder schedule
- Dependencies and blockers
- Related notes, URLs, files, and memory references
- Course/provider details where relevant
- Submission requirement and completion evidence
- Creation/update history and provenance

Provide quick filters for due today, overdue, upcoming 7 days, waiting, high priority, ready to submit, and untriaged inbox items.

## 2.2 Deadline and reminder engine

The reminder system is a first-class feature, not a prompt the model has to remember to repeat.

### Date interpretation

- Store dates as explicit timestamps with timezone where a time matters; store date-only deadlines as date-only values when the institution specifies no time.
- Resolve relative phrases such as “next Friday” against the current local date and show the resolved date to the user.
- If “the 7th” could refer to more than one month/year, ask a short clarification or create a visibly unconfirmed draft—not a silent guess.
- Distinguish due date, personal target date, reminder time, and actual submission time.
- Preserve the original natural-language request for audit and debugging.

### Reminder rules

- Support multiple reminders per task (e.g. 3 days before, 1 day before, 3 hours before).
- Allow per-item overrides and default templates by type: assignment, exam, meeting, competition, bill/admin task.
- Generate reminders from rules when a deadline is created or changed.
- Recompute reminders when the due date changes; cancel obsolete scheduled events safely.
- Use Ubuntu desktop notifications for immediate nudges and an in-app notification center for missed/queued events.
- Provide snooze, dismiss, mark complete, and open task actions.
- Support quiet hours, notification batching, escalation only for important overdue work, and user-configured lead times.
- On restart, recover pending reminders from persistent storage; do not depend only on in-memory timers.
- Log when a reminder was scheduled, delivered, snoozed, or dismissed.

### Reminder semantics

Reminders should be actionable rather than noisy. Example:

- **T−3 days:** “Draft the assignment and locate the required reference materials.”
- **T−1 day:** “Check `ds_unit2.pdf`, confirm it is the final version, and verify the Classroom destination.”
- **T−3 hours:** “Submission deadline is approaching. The file is ready; review and approve submission if correct.”

Do not state that a reminder was delivered unless the notification subsystem reports success. If the desktop session was offline or notifications were unavailable, surface missed reminders when the app resumes.

## 2.3 Guided Google Classroom workflow

This is a productivity workflow with approval boundaries. It must not claim a file was submitted unless the interface/API provides a verifiable success signal.

Target flow:

1. Parse course, assignment title, due date, and required file from natural language.
2. Match the course and assignment against connected, authorized Classroom data or the signed-in browser session.
3. If there are multiple matching courses or assignments, ask the user to select one.
4. Track the expected deliverable and its local file path.
5. Validate basic readiness: file exists, is readable, has the expected extension, is not empty, and is within known upload-size limits if available.
6. Optionally perform user-approved checks such as opening a PDF, checking page count, or running a project test suite.
7. Prepare the upload, display the exact course, assignment, file name, and due date.
8. Pause for explicit user confirmation before clicking the final Submit/Turn in action.
9. Perform submission using the supported integration or browser UI where allowed.
10. Verify the resulting state and persist evidence: confirmation message/state, timestamp, target assignment, file name, and a safe local screenshot reference if appropriate.
11. Move the task to Done only after verification. If state is ambiguous, mark it “Submission verification needed” and notify the user.

Default permissions:

- Read course list and assignment metadata: allowed after OAuth/browser authorization.
- Inspect local files in the approved workspace: allowed.
- Draft or prepare upload: allowed.
- Final submit/turn-in action: requires just-in-time explicit approval.
- Revoke, replace, or resubmit a submitted file: requires fresh approval.

The agent must not invent institutional deadlines or assume the current course is the intended destination. It should preserve manual control of the final academic submission.

## 2.4 Knowledge Rooms and graph memory

Separate knowledge by sensitivity and topic:

- Public Research
- Academic
- Projects
- Opportunities
- Operations
- Personal Vault
- Health

Each room has its own graph view, access policy, retention controls, source provenance, and audit trail. Use graph relations to connect facts and vector retrieval to find semantically relevant documents.

Personas may use a narrow, typed cross-room bridge (e.g. expose an assignment deadline to Operations without exposing the full private project notes). Bridges are visible, purpose-limited, revocable, and deny-by-default. They are not hidden bypasses.

Each memory record should track at minimum: identifier, content/reference, source, timestamp, sensitivity, room, confidence/provenance, retention policy, and permitted destinations. Store secrets in an OS keyring or dedicated secret manager, never in graph notes or prompts.

## 2.5 Personas

Initial prototype personas:

- **Task & Deadline Manager:** task capture, classification, deadline resolution, reminders, and status.
- **Exam & Study Coach:** study plans, course notes, exam preparation, assignment breakdown.
- **AI/ML Researcher:** research synthesis, citations, technical comparisons, and experiments.
- **Desktop Operator:** authorized browser and file workflows.

Future personas can include Robotics / Engineering Project Lead, Hackathon Strategist, Quantum Computing Researcher, Opportunity Scout, and Personal Assistant.

Personas are working modes, not security boundaries. A policy engine controls actual access and actions. A persona may not grant itself permission or edit the policy rules that constrain it.

## 2.6 Research council and model routing

For substantial research tasks, use a bounded workflow with four roles:

1. **Builder / Researcher:** frames the task, searches sources, and drafts the result.
2. **Red Team:** challenges assumptions and seeks counter-evidence, security weaknesses, and missing tests.
3. **Blue Team:** addresses valid objections and improves the result.
4. **Judge / Verifier:** checks claim-level evidence, citations, unresolved disagreement, and success criteria.

Use a local Gemma model through Ollama for permitted routine/private tasks. Use an approved hosted model for harder reasoning only after sensitivity checks and within explicit cost/request budgets. Provider UI automation should use dedicated browser profiles and remain compliant with each provider's rules. Use official APIs where they provide a permitted, stable integration; use browser UI automation for user-visible workflows where appropriate. Never bypass CAPTCHA, anti-bot enforcement, rate limits, or service restrictions.

The judge should not count votes. It should rank claims by evidence and source quality, identify disagreements, and label uncertainty. Model output is not a substitute for a test suite or direct source verification.

## 2.7 Desktop operation and overnight work

The platform may control browser sessions, inspect web pages, tile multiple windows, use the clipboard for long prompts, and capture targeted screenshots to diagnose UI state.

Prefer interfaces in this order:

1. Supported application API
2. Browser DOM/accessibility controls
3. Keyboard/clipboard interaction
4. Screenshot-based visual recognition
5. Raw mouse coordinates as a last resort

Use one reliable session first, then add the four-window 2×2 council after the base session has resilient recovery. Screenshots should be event-triggered or periodic only while a workflow is active; do not indiscriminately capture the desktop. Pause/redact capture on credentials, health/personal rooms, payment screens, and other sensitive surfaces.

Every overnight job must have a defined output, allowed tools/rooms/providers, budget, runtime limit, retry limit, checkpoint, approval policy, and stop condition. A background workflow must pause when it reaches a high-risk action or uncertain application state. It must never silently approve because the user is asleep.

## 2.8 Notifications and reports

Notify only for meaningful events:

- Deadline or reminder due
- Task requires a decision or approval
- Browser/session login expired
- Workflow is blocked or budget is exhausted
- Critical contradiction or risky finding
- Job completed with a report

A completed run produces:

- Short summary
- Deliverable/report link
- Sources and citations
- What was changed or submitted
- What was verified versus inferred
- Unresolved questions and uncertainties
- Actions awaiting the user
- Cost/runtime/tool-use summary where available

Use notification batching and quiet hours. Keep full trace data in the local run view rather than in push notifications.

---

# 3. User Experience and Interaction Model

## 3.1 Primary dashboard layout

The dashboard should be compact, keyboard-friendly, and optimized for low cognitive load.

**Left sidebar:**
- Inbox
- Today
- Upcoming
- Kanban
- Calendar / deadlines
- Projects
- Knowledge Rooms
- Personas
- Research Runs
- Approvals
- Reports
- Settings / Policies

**Main work area:**
- Default view: Inbox or Kanban, depending on user preference.
- Category chips or a simple category sidebar.
- Search and filters with saved views.
- Compact sticky-note/task cards that show title, status, due date, category, project, and next action.
- Drag-and-drop lane movement, with keyboard alternatives.

**Right context panel:**
- Related files and links
- Connected subject/course/project
- Deadline and reminders
- Graph relationships and source provenance
- Agent's proposed next action
- Approval/status history

The interface should not force the user to inspect every model turn. It surfaces the task state and only asks for a decision when the decision matters.

## 3.2 Core interactions

Examples of natural-language commands:

- “I have Algorithms assignment 3 due on 7 November. The file is `~/uni/daa/assignment3.pdf`.”
- “Remind me three days before, one day before, and two hours before the deadline.”
- “Split this project into five next actions, estimate effort, and put the first two on my board.”
- “Research local robot simulation frameworks overnight. Compare evidence and send me one summary when complete.”
- “Find the relevant Classroom assignment and prepare `report.pdf` for submission, but ask before turning it in.”
- “Show everything due this week, grouped by course, and flag conflicts.”

When input lacks essential information, ask the smallest necessary clarification. If the task can be saved as a draft without guessing, preserve it in Inbox and flag which details remain unresolved.

## 3.3 Calendar and deadline display

Views:
- Today: upcoming reminders and next actions.
- Upcoming 7/30 days: deadline timeline.
- Calendar: dates and scheduled work blocks.
- Overdue: unresolved expired deadlines.
- Submission tracker: required file, destination, readiness, submission state.

A deadline is a date/time constraint, not the same as the user's internal target date. Each assignment can have a personal target date earlier than the official deadline. Reminders should usually point to a useful action, not repeat “deadline soon.”

---

# 4. Technical Architecture

## 4.1 Logical architecture

```text
CLI / Local Dashboard
        |
Task Capture + Deadline Parser
        |
Persistent Task and Job Store
        |
Orchestrator / Durable State Machine
        |
Policy Engine + RBAC + Approval Queue
        |
Model Router ---- Local Gemma / Approved Hosted Models
        |
Typed Tool Registry
  |       |        |        |       |
Files  Browser  Classroom  Memory  Notifications
        |
Graph Memory + Vector Retrieval + Provenance
        |
Audit Trail + Checkpoints + Reports
```

## 4.2 Recommended prototype stack

- **Language:** Python
- **CLI:** Typer + Rich
- **Local HTTP/UI backend (optional initially):** FastAPI
- **Dashboard:** lightweight local web UI; do not block the first usable prototype on a large frontend
- **Local model:** Ollama with Gemma 4 E2B first; test E4B against available memory
- **Hosted model:** configurable provider adapter, enabled only by the user
- **Structured persistence:** SQLite for tasks, reminders, approvals, job state, audit metadata, and graph relationships
- **Semantic retrieval:** local Qdrant or a lightweight local vector store
- **Embedding model:** local EmbeddingGemma-compatible runtime
- **Browser:** Playwright with a dedicated automation browser profile
- **Google integration:** Google OAuth with minimal read-only scopes first; Classroom submission only after workflow verification and explicit approval
- **Notifications:** desktop notification command/system API plus a persistent in-app notification queue
- **Versioning:** Git worktree/branch for repo modifications
- **Secrets:** OS keyring or secret store; never plaintext in source control

Keep dependencies modular. The core task tracker, reminder service, policy engine, and local memory should still work if hosted inference or a particular browser provider is unavailable.

## 4.3 Core services

### Task service

Creates, updates, filters, relates, and closes tasks. Validates state transitions and persists task history. Natural-language extraction must produce a typed candidate object before any durable update.

### Deadline and reminder service

Stores the official deadline, personal target date, reminder rules, and delivery state. Schedules reminder records persistently. Reconciles reminders whenever deadlines change. Supports recovery after restart and a missed-reminder queue.

### Orchestrator

Runs a durable state machine. A job consists of steps, tool calls, outputs, and checkpoints. It resumes from a checkpoint after interruption instead of restarting the full run. It enforces time, retry, token/API, browser-action, and storage budgets.

### Policy engine

Authorizes each tool call independently of model instructions. Inputs include requesting persona, room, data sensitivity, action type, target resource, provider destination, risk tier, and approval record. Fail closed if policy cannot be evaluated.

### Model router

Chooses a model based on capability needs, privacy classification, latency, cost/budget, and provider availability. Private or blocked context stays local. The router records model/provider and data categories sent; it should not log secrets or full sensitive prompts by default.

### Tool registry

Every tool has a schema, description, permission requirement, risk tier, timeout, validation rules, output schema, and audit hooks. The model can select only registered tools available to its current policy context.

### Memory service

Supports graph traversal, semantic retrieval, provenance, sensitivity labels, and cross-room bridges. Retrieval must check access permission before returning content—not retrieve everything and filter only in the UI.

### Browser controller

Owns browser sessions, allowed domains, tab/window identity, screenshot capture policy, navigation and action verification. It must distinguish “action attempted” from “action succeeded.”

### Report and notification service

Generates final reports and small actionable notifications. Saves report artifacts locally and links to supporting evidence and the run log.

---

# 5. Data Model (Initial)

SQLite tables or equivalent typed models:

## `tasks`

- `id`
- `title`
- `description`
- `item_type`
- `status`
- `priority`
- `category_id`
- `project_id` (nullable)
- `room_id`
- `persona_owner` (nullable)
- `due_at` (nullable)
- `due_date` (nullable for date-only institutional deadlines)
- `timezone`
- `personal_target_at` (nullable)
- `estimated_minutes` (nullable)
- `source_text`
- `created_at`, `updated_at`, `completed_at`
- `completion_evidence` (nullable reference)

## `reminders`

- `id`, `task_id`
- `scheduled_at`
- `reminder_type` (lead-time, milestone, overdue, blocker)
- `message`
- `status` (scheduled, delivered, snoozed, dismissed, missed, cancelled)
- `delivery_channel`
- `delivered_at` (nullable)
- `rule_snapshot`

## `attachments`

- `id`, `task_id`
- `path_or_uri`
- `display_name`
- `mime_type`, `size_bytes`, `checksum` (where practical)
- `provenance`, `created_at`
- `sensitivity_label`

## `submissions`

- `id`, `task_id`
- `platform` (e.g. Google Classroom)
- `course_id`, `course_name`
- `assignment_id`, `assignment_name`
- `file_attachment_id`
- `state` (not-ready, prepared, awaiting-approval, submitting, submitted, verification-needed, failed)
- `approval_id` (nullable)
- `submission_timestamp` (nullable)
- `verification_evidence` (nullable reference)

## `projects`, `categories`, `rooms`, `personas`

Persist display settings and stable identifiers separately from tasks. Do not use display names alone as access-control identifiers.

## `graph_nodes` and `graph_edges`

Nodes contain type, room, sensitivity, source, and metadata. Edges contain source, relation type, target, provenance, and policy attributes. Validate allowed relation types and cross-room permissions.

## `jobs` and `job_steps`

Persist task goal, scope, budget, current step, status, checkpoint, retry count, start/end times, and report reference. Each step records its inputs/outputs as safe references, not unbounded secret-bearing prompts.

## `approvals`

Record the exact proposed action, normalized arguments or action hash, requester, approver, reason, expiration, decision, and execution status. Any material change to action arguments invalidates the approval.

## `audit_events`

Record actor/persona, action, target, policy result, approval reference, timestamp, result, and rollback/evidence reference. Restrict modification and keep logs free of secrets.

---

# 6. Security, RBAC, and Autonomy Policy

## 6.1 Risk tiers

- **Tier 0 — Read:** search authorized files, query accessible memory, inspect allowed sites and authorized service data.
- **Tier 1 — Prepare:** draft content, commands, plans, messages, code diffs, and proposed submissions without applying the final action.
- **Tier 2 — Reversible workspace write:** change files inside an approved workspace with pre-change checkpoint/diff and recovery path.
- **Tier 3 — External or destructive action:** send messages, submit coursework, publish, delete important files, alter account settings, or make purchases; require explicit approval for the exact action.
- **Tier 4 — Privileged system action:** `sudo`, security configuration, credential access, permission changes, and system-wide installs; require separate elevated approval with command/impact preview.

No model receives an unrestricted root shell. Prefer narrow, pre-registered operations over arbitrary command strings. Approval does not turn an unsafe command into a safe one; deny rules remain enforceable.

## 6.2 Data sensitivity and cloud policy

Suggested labels:

- Public
- Internal / non-sensitive
- Personal
- Sensitive personal
- Restricted (health, credentials, authentication artifacts)

A cloud request must be checked against the room policy and data labels before prompt construction. Personal Vault and Health Room are excluded from cloud use by default. A user-configured exception should be narrow, explicit, revocable, and logged. Authentication tokens and browser cookies are never context for model reasoning.

## 6.3 Browser and prompt-injection defense

- Treat web content, emails, PDFs, screenshots, and tool outputs as untrusted data.
- Retrieved content may inform an answer but cannot override system policy or instruct the agent to disclose other rooms.
- Separate planning from execution; validate every tool argument in code.
- Scope browser sessions by provider and allowed domains.
- Keep sessions isolated and never transfer cookies or account context between providers.
- Stop on unexpected login, consent, CAPTCHA, anti-automation, payment, or permission-changing screens.

## 6.4 Approvals

An approval is bound to a specific action, resource, and argument set; it expires and cannot be reused for modified arguments. User confirmation must show a human-readable preview, including destination, file, recipient, or command effects. High-risk actions require a fresh approval even if the broader task was previously approved.

## 6.5 Stop and recovery

- Global pause and kill switch
- Per-job cancel/pause/resume
- Maximum duration and tool-call budgets
- Retry caps and backoff
- Detect repeated unchanged failure
- Checkpoint after each meaningful stage
- Never retry external submission blindly after ambiguous state
- Keep rollback references for supported local changes

---

# 7. Eight-Hour Prototype Plan

The eight-hour target is a narrow demonstrator, not the full product. Favor one coherent end-to-end workflow over many half-finished integrations.

## Hour 1 — Repository, data store, and CLI

- Create the Python project and virtual environment.
- Implement SQLite initialization and migrations/schema creation.
- Add CLI commands: `capture`, `tasks`, `show`, and `board`.
- Add task/category/status data structures.
- **Exit check:** capture a task and retrieve it after restarting the CLI.

## Hour 2 — Inbox, Kanban, and category model

- Implement Inbox, Next, In Progress, Waiting, Review, Ready to Submit, Done.
- Add categories and basic filters.
- Add commands for changing status/category and viewing overdue/upcoming work.
- **Exit check:** move an item through at least three states and preserve its history.

## Hour 3 — Natural-language task and deadline parsing

- Use local Gemma to extract title, subject/category, due date, expected file, reminder plan, and destination from natural language into a typed JSON candidate.
- Validate all fields in deterministic code.
- Ask for clarification when date/month/year, course, or assignment is ambiguous.
- Add personal target date and official due-date distinction.
- **Exit check:** create a task from a sample sentence and verify the resolved date before persistence.

## Hour 4 — Persistent reminders and desktop notifications

- Add reminder rules and a persistent scheduler/reconciliation loop.
- Add desktop notifications with click-through to the related task.
- Handle snooze, completion, and missed reminders after restart.
- **Exit check:** schedule a near-term test reminder, deliver it, and confirm delivery state is logged.

## Hour 5 — File readiness and safe action approvals

- Add attachment path validation and checksums where practical.
- Implement Tier 0–3 decision objects and an approval queue.
- Build an exact-action approval screen/CLI confirmation.
- Add Git diff/worktree helper for tracked project changes.
- **Exit check:** a submission action cannot execute until approved; changed arguments invalidate approval.

## Hour 6 — One browser workflow

- Configure one dedicated Playwright browser session and allowed-domain list.
- Implement navigation, page-state inspection, screenshot-on-error, and safe stop behavior.
- Manually sign in; do not import the everyday profile wholesale.
- **Exit check:** open a target page, inspect its state, save a safe run artifact, and stop correctly on an unexpected dialog.

## Hour 7 — One education-service integration path

Choose one path based on available credentials and time:

- Preferred: read-only Google Classroom course/assignment matching plus a prepared submission state; or
- Fallback: browser-assisted, human-verified preparation where official integration setup is not ready.

The demonstrator must not falsely report an upload as complete. Final Turn in/Submit remains behind explicit approval.

**Exit check:** the system can match or request selection of the target course/assignment, confirm the file, and produce an approval-bound submission preview.

## Hour 8 — End-to-end test and executive demo

- Test task capture → deadline resolution → reminders → file association → submission preparation → approval gate → verification state.
- Test ambiguous dates, missing files, duplicate assignment matches, expired approval, and interrupted browser state.
- Write setup/limitations instructions and capture a short demo workflow.
- **Exit check:** one workflow succeeds end-to-end without claiming unverified completion.

### Defer until after the eight-hour demonstrator

- Four simultaneous consumer AI browser sessions
- Full knowledge graph UI and cross-room bridge management
- Health and sensitive personal rooms
- Multiple provider adapters
- Full Gmail and Classroom write operations
- Complex autonomous coding with `sudo`
- Long-running overnight scheduler with reboot recovery
- Advanced visual UI automation across arbitrary desktop applications

---

# 8. Roadmap After the Prototype

## Phase 1 — Reliable productivity core

- Full tracker UI and responsive Kanban
- Calendar/deadline views, recurring reminders, quiet hours
- Reliable reminder delivery and restart recovery
- Assignment templates by subject/course
- Local report and notification center
- Import/export and backup/restore

## Phase 2 — Context and memory

- Room-scoped knowledge graph
- Semantic retrieval and source citations
- Cross-room bridge creation/revocation and audit
- Persona-specific views and tools
- Memory expiration, correction, and deletion controls

## Phase 3 — Application integrations

- Classroom read-only data and guided submit flow
- Gmail read-only search and draft preparation
- Calendar event integration
- Browser workflows with resilient state detection
- More sites via small adapters, subject to permissions and service rules

## Phase 4 — Overnight orchestration

- Persistent job queue and checkpoints
- Budgets, retries, progress milestones, and report generation
- One research session, then red/blue/judge stages
- Four tiled browser sessions only after single-session reliability is measured
- Quiet notifications and local run viewer

## Phase 5 — Advanced desktop operator

- Accessibility/DOM-first desktop interaction
- Screenshot-based fallback with privacy protections
- Window tiling and session health monitoring
- Approved file operations through policy-scoped tools
- Git worktree workflows and test-driven verification
- Safe integration with system-level tasks; no unrestricted model-controlled root

## Phase 6 — Hardening and distribution

- Threat model and security tests
- Database encryption/backup strategy where appropriate
- Audit integrity and retention controls
- Resource/cost dashboards
- Provider compatibility tests and graceful degraded mode
- Packaging/service installation for Ubuntu

---

# 9. Acceptance Criteria

## Productivity

- A natural-language assignment becomes a structured task with the correct course, category, deadline, expected file, and reminder rules.
- Ambiguous dates are clarified rather than guessed.
- Kanban moves and category updates persist across restarts.
- The user can inspect all tasks due today, this week, overdue, and ready to submit.
- Reminder delivery and snooze/dismiss states are persistent and auditable.

## Submission workflow

- The agent identifies the target course/assignment or asks the user to choose among matches.
- It verifies that the expected file exists and is readable.
- It shows the exact submission target and file before requesting approval.
- It does not submit until the precise final action is approved.
- It marks the item Done only after receiving a reliable verification signal.
- An ambiguous upload state becomes “verification needed,” not a blind retry.

## Memory and privacy

- Retrieval checks room permission before returning data.
- Cross-room bridges disclose only explicitly approved fields and can be revoked.
- Restricted room data is excluded from cloud prompts by default.
- Secrets and authentication artifacts never enter prompts, graph data, Git, or ordinary logs.

## Agent autonomy

- Jobs can be paused, resumed, inspected, and cancelled.
- Every tool action has a policy decision and an audit event.
- The system stops safely on unknown UI states, budget exhaustion, or approval requirements.
- Local file changes have diff/checkpoint and rollback references where supported.
- Reports separate verified facts, sourced claims, model inference, and unresolved uncertainty.

## Reliability

- A restart does not lose tasks or pending reminders.
- Repeated failure is bounded by retry limits.
- The UI distinguishes proposed, attempted, successful, failed, and unverified actions.
- Notifications are meaningful and do not fire for every model turn.

---

# 10. Key Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Ambiguous dates or wrong course | Display resolved dates; ask when month/year/course match is ambiguous |
| Reminder lost after crash | Persistent scheduled records and startup reconciliation |
| False claim of successful submission | Verify target state; use “verification needed” on ambiguity |
| Browser interface changes | DOM/accessibility first, state checks, screenshots on failure, bounded retries |
| Prompt injection from websites or documents | Treat retrieved content as untrusted; enforce policy outside the model |
| Sensitive data leaks to cloud | Data labels, deny-by-default rooms, selective retrieval, pre-send policy checks |
| Destructive terminal command | Typed tools, sandbox, diff/checkpoint, exact-action approval, no unrestricted root shell |
| Notification fatigue | Quiet hours, batching, priority levels, event-based notifications |
| Agent loops indefinitely | Step budgets, runtime limits, max retries, stable stopping criteria |
| Four-model council produces confident nonsense | Claim-level citation checks, primary-source review, deterministic tests, uncertainty labels |
| Provider UI automation violates terms or breaks | Use supported routes, provider-specific constraints, no bypass of anti-bot controls |
| Scope overwhelms prototype | Ship one end-to-end deadline/submission workflow first; defer four-window orchestration |

---

# 11. Suggested Repository Layout

```text
ubuntu-agent/
├── pyproject.toml
├── README.md
├── .env.example
├── agent/
│   ├── cli.py
│   ├── config.py
│   ├── orchestrator.py
│   ├── router.py
│   ├── policy.py
│   ├── approvals.py
│   ├── audit.py
│   ├── notifications.py
│   ├── tasks/
│   │   ├── service.py
│   │   ├── parser.py
│   │   ├── kanban.py
│   │   └── deadlines.py
│   ├── reminders/
│   │   ├── scheduler.py
│   │   └── delivery.py
│   ├── memory/
│   │   ├── rooms.py
│   │   ├── graph.py
│   │   ├── retrieval.py
│   │   └── bridges.py
│   ├── tools/
│   │   ├── registry.py
│   │   ├── filesystem.py
│   │   ├── browser.py
│   │   ├── classroom.py
│   │   └── git.py
│   ├── integrations/
│   │   ├── ollama.py
│   │   ├── hosted_models.py
│   │   └── google_auth.py
│   └── reports/
│       └── generator.py
├── ui/                         # Optional local dashboard
├── data/                       # Runtime data; excluded from Git
├── reports/                    # Generated reports; sensitive by default
└── tests/
    ├── test_task_parser.py
    ├── test_deadlines.py
    ├── test_approvals.py
    ├── test_room_access.py
    └── test_submission_state.py
```

Use `.gitignore` for `.env`, tokens, OAuth client secrets, browser profiles, runtime databases, screenshots, private reports, and model artifacts. The project must never commit personal data or authentication state.

---

# 12. Final Product Principle

**Make the agent highly autonomous at organizing, researching, planning, and reversible work; make it explicit and permission-bound at privacy boundaries, privileged system actions, and external submissions.**

The task tracker is the user's operational source of truth. The agent can create and update tasks, turn intent into reminder schedules, prepare files, research, and run overnight workflows. The user should not have to remember what to ask next—but must remain able to inspect, correct, pause, or stop the system at any time.
