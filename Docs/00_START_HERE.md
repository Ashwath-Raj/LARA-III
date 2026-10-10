# Ubuntu Agent — Documentation Entry Point

## Product promise

Give the agent an outcome and receive useful work without coordinating every AI step. Ubuntu Agent is a local-first Ubuntu productivity operator for task capture, deadlines, reminders, research, persistent memory, and guarded desktop actions.

## How to use this documentation

These files are implementation contracts. Read the relevant contracts before changing code. Do not copy requirements into multiple documents; update the document that owns the requirement and link to it elsewhere.

| File | Canonical responsibility |
|---|---|
| `00_START_HERE.md` | Document index, development rules, prototype boundary |
| `01_FEATURES_EXECUTIVE_OVERVIEW.md` | Product value proposition and executive feature summary |
| `02_UBUNTU_AGENT_PLAN.md` | Product/engineering plan, 8-hour prototype sequence, broad roadmap |
| `03_DATA_AND_CHUNKING.md` | Persistent entities, database schema, graph model, document chunking and retrieval |
| `04_SECURITY_PIPELINE.md` | Runtime security enforcement and approval lifecycle |
| `05_ARCHITECTURE.md` | Component boundaries, dependency direction, runtime flows and state-machine responsibilities |
| `06_API_CONTRACT.md` | Internal API request/response shapes, endpoints, events and error semantics |
| `07_UI_UX_SPEC.md` | Screens, navigation, interaction states and user-visible behaviour |
| `08_DESIGN_LANGUAGE.md` | Visual tokens, typography, surfaces, motion and component styling |
| `09_AUTONOMY_POLICY_MATRIX.md` | Default permissions by persona, room, action and risk tier |
| `10_INTEGRATION_MATRIX.md` | Provider and application integration capabilities, authentication and limits |
| `11_OPERATIONS_AND_RECOVERY.md` | Startup, jobs, reminders, recovery, backups, logs and emergency stop |

## Source-of-truth rules

- Product scope and the short-term build commitment live in `01_FEATURES_EXECUTIVE_OVERVIEW.md` and `02_UBUNTU_AGENT_PLAN.md`.
- `03_DATA_AND_CHUNKING.md` owns persistence schemas and retrieval behaviour.
- `04_SECURITY_PIPELINE.md` owns how a proposed operation is authorized, approved, executed and audited.
- `09_AUTONOMY_POLICY_MATRIX.md` owns the default permission decisions. The security pipeline implements these decisions; it must not invent alternate permissions.
- `05_ARCHITECTURE.md` owns module/service boundaries. `06_API_CONTRACT.md` owns request/response shapes.
- `07_UI_UX_SPEC.md` owns screen behaviour. `08_DESIGN_LANGUAGE.md` owns visual styling.
- `10_INTEGRATION_MATRIX.md` owns provider-specific capability and limitation statements.
- `11_OPERATIONS_AND_RECOVERY.md` owns runtime lifecycle, backup and recovery procedures.

If two documents conflict, do not quietly choose one. Record the conflict and update the canonical owner before implementing the affected feature.

## Initial prototype boundary

The first prototype proves one end-to-end productivity flow:

1. Capture an assignment from natural language.
2. Parse and confirm the due date, subject/course, expected file and reminder schedule.
3. Store it persistently and display it in the Inbox/Kanban view.
4. Schedule reminders that survive application restarts.
5. Confirm the correct Google Classroom course and assignment.
6. Validate the file and prepare the submission.
7. Require fresh, explicit approval for the final Submit/Turn in action.
8. Verify the result or mark it as needing verification; never infer success from a click.

Use one reliable browser workflow and one education integration path. The four-session AI council, broad desktop control, advanced graph visualization and sensitive Personal/Health rooms are later milestones. See `02_UBUNTU_AGENT_PLAN.md` for the hour-by-hour sequence.

## Development rules for coding agents

1. Inspect the existing repository before adding or replacing modules. Reuse existing patterns when they satisfy these contracts.
2. Implement the smallest coherent vertical slice before adding more providers, personas or tools.
3. Use typed inputs/outputs and deterministic validation around model-generated data. Model output is untrusted input.
4. Never execute model-generated shell text directly. Tools must be registered, schema-validated and policy-checked.
5. Keep user data, OAuth credentials, browser profiles, runtime databases and private reports out of Git.
6. Add tests with every new contract or permission rule. A feature is not complete because the happy path works.
7. Distinguish `proposed`, `attempted`, `succeeded`, `failed` and `unverified` states. Do not fabricate completion.
8. When a requirement is unclear, preserve data safely and ask for clarification rather than guessing.
9. Keep dependencies modular. Local task capture, persistence, reminders and policy enforcement must not depend on a hosted model.
10. Update the owning document when an implementation decision changes the contract.

## Repository conventions

- Python-first application logic.
- Use type hints and Pydantic models at boundaries.
- Use database migrations rather than ad-hoc schema mutation.
- Make asynchronous jobs persistent and resumable.
- Use explicit time zones for timestamps; distinguish a date-only deadline from a timestamp.
- Use structured logging with secret redaction.
- Keep tests deterministic by injecting clocks, provider clients and tool executors.

## Definition of done

A change is ready when its behaviour is implemented, relevant permission checks exist, errors and uncertain outcomes are represented honestly, tests pass, sensitive data is not leaked, and the owning documentation is consistent with the code.
