# UI/UX Behaviour Specification

## Scope

This document owns screen structure and interaction behaviour. `08_DESIGN_LANGUAGE.md` is the authority for palette, fonts, visual tokens, motion and component styling. Product priorities are in `01_FEATURES_EXECUTIVE_OVERVIEW.md`.

The UI must reduce cognitive load: show the user's current work, next action and genuine blockers without forcing them to inspect every model turn.

## Main desktop shell

Use three regions:

1. **Left navigation rail:** collapsible navigation for Inbox, Today, Upcoming, Kanban, Calendar, Projects, Knowledge Graph, Personas, Runs/Reports, Approvals and Settings. Group knowledge rooms separately and show sensitivity indicators only for rooms the user may access.
2. **Central workspace:** current chat, task board, calendar, graph, integration screen or report.
3. **Context drawer:** optional right panel for task details, source evidence, relationships, active permissions, action history or a job trace.

The sidebar should remain stable across views. Switching pages should not discard an unsaved composer draft or an in-progress task edit.

## Primary screens

### Inbox

Purpose: capture first, categorize later.

- Accept natural-language text, URLs and local file references.
- Show new captures as untriaged items.
- Offer suggested title, category, due date, project and next action; suggestions remain editable.
- Display unresolved fields without silently inventing them.
- Allow conversion to task, assignment, idea, research job or follow-up.
- Never silently archive or discard a capture.

### Kanban and task detail

Default lanes: Inbox, Next, In Progress, Waiting, Review, Ready to Submit, Done and Archived.

A card should show title, status, due date, primary category and next action. Secondary data belongs in the detail drawer. Drag-and-drop must have keyboard/menu alternatives and a clear undo affordance. Persist a move before showing it as definitively saved; if the write fails, restore the prior state and explain why.

Task detail includes:

- Official due date and separate personal target date
- Reminder timeline with scheduled/delivered/missed states
- Category, project, course and room
- Related files and links
- Dependencies/blockers and next action
- Proposed agent action and its required permission
- Activity and completion evidence

### Today, Upcoming and Calendar

- Today prioritizes deadlines, reminders, active work and approvals.
- Upcoming supports 7-day and 30-day horizons.
- Calendar differentiates official deadlines from planned work sessions and reminder times.
- Overdue tasks remain visible until resolved or explicitly dismissed according to the user's configured rules.
- A date without a known month/year remains unconfirmed and cannot create precise reminders.

### Chat and agent run

- Use a white reading surface against the smoky application frame.
- The composer accepts an outcome, not just a question. Show active room and whether local/cloud processing is allowed.
- Display a concrete run phase: `Planning`, `Researching`, `Reviewing`, `Waiting for approval`, `Executing` or `Verifying`.
- Collapse routine tool traces by default while making them inspectable.
- Expose Pause, Stop and Inspect controls for long-running jobs.
- Do not show fake progress percentages for open-ended reasoning.
- If a job is blocked, state what stopped, what was completed, and the smallest available next action.

### Knowledge graph and rooms

- Graph exploration uses permission-filtered data from the backend. Hiding a node only in the browser is not access control.
- Selecting a node opens a detail drawer with relationships, permitted source evidence and last update.
- `Why connected?` shows the typed path and provenance.
- `Trace information flow` shows allowed cross-room bridge source, destination, purpose and shared fields.
- Restricted nodes and even their existence must not appear in unauthorized views or autocomplete results.
- A room selector must show the active room before retrieval or disclosure-sensitive actions.

### Runs and reports

Run detail shows goal, status, start time, current stage, scope, budget usage, checkpoints, pending approval, and source/artifact references. Reports show an executive summary first, then evidence, sources, decisions, uncertainty and next actions. Separate verified results from model inference.

## Approval surfaces

Any approval dialog must show:

- Plain-language action and reason
- Exact target/resource and normalized arguments
- Source/destination rooms and whether data leaves the machine
- Policy basis and risk tier
- Expected side effect and reversibility
- Preview of the actual command, diff, recipient, assignment or attachment as applicable
- Approval expiry and what specifically is being approved

Buttons must be specific, e.g. `Approve upload to Data Structures / Assignment 3`, not just `OK`. Approval must not authorize changed arguments or future actions. High-risk approvals cannot be reduced to a one-click notification action.

For Google Classroom show the course, assignment, due date if known, file name and size, then distinguish `Prepared`, `Submitted` and `Submission verified`. If verification is unavailable, show `Status unknown — check Classroom`.

## Notifications

Native Ubuntu notifications are brief entry points, not the source of truth. Each notification links directly to the relevant task or run and exposes one useful next action.

Notify on deadlines, approval requests, blockers, critical contradictions and completion. Support quiet hours, snooze and missed-event recovery. Do not notify for every model call. Completion notices must link to the full local report.

## Loading, errors and empty states

- Show the current meaningful stage while loading.
- If a service fails, preserve the task/job and offer retry only when safe.
- If external action status is uncertain, do not display success; route to verification.
- Empty screens should offer one concrete next action rather than decorative illustrations.
- Permission denial should explain the blocked action and permitted alternative without revealing protected data.
- If cloud routing is blocked, state that the task can continue locally or wait for user policy changes.

## Accessibility and keyboard

- Support keyboard navigation, visible focus and Escape-to-close for dialogs/drawers.
- Provide labels for icon-only controls.
- Announce meaningful status changes, not every generated token.
- Meet WCAG AA contrast for ordinary text and interactive states.
- Do not communicate room, risk or task status by colour alone.
- Honour reduced-motion preference.
- Do not make essential actions hover-only.

## UI state contract

Every meaningful operation should distinguish at least `idle`, `loading`, `ready`, `saving`, `saved`, `blocked`, `failed` and `unverified` where relevant. The backend remains authoritative. UI optimism must have a rollback path if persistence fails.

## Out of scope for first pass

Avoid building a complex animated graph, unrestricted remote desktop control, four independent AI browser windows and extensive configuration screens before Inbox → deadline → reminder → submission preparation works end-to-end.
