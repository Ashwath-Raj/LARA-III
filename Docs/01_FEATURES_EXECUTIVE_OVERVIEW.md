# Ubuntu Agent — Executive Feature Overview

## Product in one sentence

A local-first Ubuntu productivity operator that turns natural-language goals into organized tasks, deadlines, reminders, research, and guarded desktop actions—then reports only what needs the user's attention.

## The problem

Students and technical builders spread work across terminal sessions, browser tabs, AI chats, Google Classroom, notes, PDFs, deadlines, project repositories, and competition portals. The cost is not simply doing the work; it is remembering what exists, deciding the next step, moving context between tools, repeatedly prompting models, and verifying whether actions actually completed.

Ubuntu Agent reduces that orchestration burden by maintaining a persistent task system and a permissioned context layer while automating bounded portions of the workflow.

## Core value proposition

**Give it an outcome, not a sequence of clicks.** The system decomposes the goal, organizes the work, sets reminders, retrieves relevant context, uses local or approved cloud models, runs bounded research/review cycles, and returns a concise summary plus evidence.

## Executive feature set

### 1. Personal productivity hub

- Persistent Inbox for quick capture of tasks, ideas, links, and files.
- Kanban board with Inbox, Next, In Progress, Waiting, Review, Ready to Submit, Done, and Archived states.
- Category sidebar for Academics, Projects, Hackathons, AI/ML, Robotics, Quantum, Opportunities, and Personal/Admin.
- Sticky-note cards with priority, due date, next action, category, project, files, and activity history.
- Today, Upcoming, Overdue, and Ready to Submit views.

### 2. Natural-language task and deadline management

Example: “My Algorithms assignment is due on 7 November. The file is `assignment3.pdf`. Remind me three days before and help prepare it for Classroom submission.”

The agent resolves the date, creates the task, attaches the file, assigns the course/category, generates reminders, tracks readiness, and prepares a submission workflow. It asks when essential details are ambiguous instead of silently guessing.

### 3. Reliable reminder system

- Multiple reminders per task and configurable default templates.
- Persistent scheduling with restart recovery.
- Ubuntu desktop notifications and an in-app notification center.
- Quiet hours, snooze, missed-reminder recovery, and event-based alerts.
- Notifications link directly to the relevant task and next action.

### 4. Guided Google Classroom workflow

- Find or confirm the exact course and assignment.
- Check that the requested file exists and is readable.
- Prepare the upload and display the exact file and destination.
- Require explicit approval before the final Submit/Turn in action.
- Verify the resulting state before marking the task Done.

### 5. Compartmentalized memory

- Separate Academic, Projects, Opportunities, Operations, Public Research, Personal Vault, and Health Rooms.
- Graph relationships connect people, courses, tasks, files, projects, and deadlines.
- Semantic retrieval finds relevant information by meaning.
- Narrow, auditable cross-room bridges share only approved fields.
- Sensitive rooms are excluded from cloud prompts by default.

### 6. Purpose-specific personas

Initial personas: Task & Deadline Manager, Exam & Study Coach, AI/ML Researcher, and Desktop Operator. Future modes may cover robotics, quantum computing, hackathons, and opportunities. Personas provide specialized workflows but do not bypass central permissions.

### 7. Local-first model routing

- Local Gemma via Ollama for appropriate private and routine tasks.
- Optional hosted reasoning for harder tasks where the sensitivity policy permits it.
- Selective context transfer, provider-level controls, cost/runtime budgets, and safe fallback.
- The user's memory remains in the local platform; only task-approved context is sent externally.

### 8. Multi-model research and quality control

A bounded four-role workflow:

- Builder/Researcher gathers evidence and drafts.
- Red Team challenges assumptions and searches for counter-evidence.
- Blue Team addresses valid objections and improves the result.
- Judge/Verifier checks citations, disagreement, uncertainty, and success criteria.

The system prioritizes cited evidence and test results over model consensus.

### 9. Desktop and browser operator

- Prefer APIs and accessible browser controls where appropriate.
- Use a dedicated browser profile for automation.
- Support prompt insertion, window tiling, targeted screenshots, state checking, and recovery from common UI failures.
- Four-session 2×2 browser council is a later milestone after single-session reliability.
- No bypass of provider safeguards, CAPTCHAs, rate limits, or access controls.

### 10. Overnight jobs and reports

- Start a task with one outcome-focused instruction.
- Persist checkpoints, retry limits, budgets, and stopping criteria.
- Pause for approval on high-risk or uncertain actions.
- Receive low-noise notifications at completion, blockers, important findings, or approval needs.
- Produce a report with summary, sources, evidence, decisions, uncertainty, and next actions.

### 11. Safety, RBAC, and reversibility

- Central authorization for every tool call.
- Read, prepare, reversible-write, external/destructive, and privileged-system risk tiers.
- Exact-action approvals for submissions, sending, deletion, publishing, and privileged operations.
- Git branches/worktrees, diffs, tests, checkpoints, and audit logs for local changes.
- No unrestricted model-controlled root shell; use least privilege and a global pause/kill switch.

## Eight-hour prototype commitment

The initial demo should prove one coherent workflow:

1. Capture an assignment in natural language.
2. Resolve and display the due date.
3. Place it on the Kanban board with the correct category and file.
4. Schedule persistent reminders and deliver a desktop notification.
5. Locate or select its Google Classroom destination.
6. Prepare a submission preview.
7. Require explicit approval for the final submission.
8. Verify the outcome or clearly report that verification is still needed.

The initial build should support a single reliable browser workflow, local Gemma parsing, SQLite persistence, and one read-only education integration or a browser-assisted fallback. Four parallel AI sessions, extensive graph UI, sensitive personal/health rooms, and broad desktop control are later phases.

## Success measures

- Natural-language task capture is reliable and ambiguous dates are clarified.
- Tasks, statuses, and reminders persist across restart.
- Every assignment has a visible due date, file state, and next action.
- Submission is never reported as successful without a verification signal.
- Sensitive room data is not included in cloud prompts by default.
- No action exceeds persona permissions or runs without required approval.
- Research reports contain source evidence and visible uncertainty.
- Notifications are useful rather than continuous.
- The user can pause, inspect, resume, or cancel any running job.

## Guiding principle

**Autonomous coordination, controlled execution.** The agent should carry the cognitive load of organizing and progressing work, while the user retains clear control over data disclosure, system privileges, and external actions.
