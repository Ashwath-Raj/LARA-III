# Integration Matrix

## Principles

Prefer stable supported interfaces over coordinate-based UI control. Every integration must declare capabilities, permissions, data sent/received, failure states, verification strategy and whether it has external side effects.

Integration availability is configuration-dependent. Do not assume a model, API feature or provider page is available merely because an adapter exists.

## Integration inventory

| Integration | Initial role | Authentication/data boundary | Failure and verification rules |
|---|---|---|---|
| Ollama + Gemma | Local generation and structured tool proposals | Local endpoint; no cloud disclosure by default | Health-check endpoint/model availability; timeout and return `provider_unavailable` rather than silently switching to cloud |
| Local embedding model | Create embeddings for permitted local content | Process only content whose room policy allows local indexing | Verify dimensions/model identity; re-index on model change; deletion propagates to vector store |
| Hosted Gemma / Gemini API | Optional higher-capability reasoning | User-configured API key stored as a secret; pre-send sensitivity checks | Enforce call/time/cost budgets; surface quota/permission errors; never auto-fallback to another unconfigured provider |
| Other hosted AI providers | Optional research/review sessions | Separate provider configuration and isolated sessions | Use a supported API where appropriate; do not share credentials, cookies or hidden chat context across providers |
| Playwright browser controller | Browser reading, selected web workflows and visible automation | Dedicated browser profile per account/provider; manual sign-in initially | Prefer DOM/accessibility locators; screenshot on errors; stop on unexpected state, CAPTCHA, anti-bot or consent screen |
| Google Classroom API | Read courses/assignments and match targets | OAuth with minimum read-only scopes at first | Reauthorization required if consent expires; distinguish lookup from submission; verify state through authoritative result |
| Google Classroom browser workflow | Prepare upload or interact when a supported API path is unavailable and permitted | Dedicated signed-in browser context; never copy the everyday browser profile wholesale | Exact course/assignment/file check; final Turn in requires fresh approval; ambiguous state becomes `verification_needed` |
| Gmail API | Later phase: read authorized messages and prepare drafts | Minimum OAuth scopes; read-only before draft/send scopes | No sending without separate approval; redact content from logs; reauthorization on consent failure |
| Local filesystem | Workspace search, file checks and approved file operations | Workspace allowlist and OS user permissions | Canonicalize path, reject traversal/symlink escapes, check file type/size, verify every write |
| Git | Branch/worktree, diff, tests and rollback for tracked code | Operate only in configured repositories | Check dirty state before work; never overwrite user changes; Git does not reverse external side effects or protect all untracked files |
| Qdrant local mode | Semantic search over allowed document chunks | Local storage, room-filtered payloads and access re-check before returning content | Degrade to permitted metadata/keyword search; never bypass room checks when unavailable |
| SQLite | Structured tasks, reminders, approvals, jobs, audit metadata and graph relations | Local application-data directory with OS permissions | Migrations, foreign keys, transactions, backup/restore tests and integrity checks |
| Ubuntu notifications | Local reminder nudges through `/usr/bin/notify-send` | Local desktop session | Fixed argv, `shell=False`, bounded text and timeout; unavailable delivery retries then becomes `missed`; crash after display and before persistence may duplicate delivery |
| MCP tool servers | Future common connector protocol | Each server has separate trust and permissions | Register servers explicitly, inspect tool schemas, apply the same policy checks, restrict network and filesystem scope |

## Google Classroom workflow

### Initial capability

Begin with read-only course and assignment discovery. Store only stable IDs and the metadata needed by task matching. The agent should match by course and assignment identifiers where available, not by title alone.

### Submission preparation

Before preparing an upload:

1. Confirm the course and assignment.
2. Confirm the local file path, name, type and readability.
3. Ensure the file is attached to the current task.
4. Display the exact target and operation in the UI.
5. Request a fresh approval before the final Turn in/Submit action.
6. Perform the operation only through an allowed adapter.
7. Verify the resulting state and store evidence.

Do not blindly retry a submit operation after a timeout; the original action may have succeeded remotely. Check the target state first. If the result remains ambiguous, stop at `verification_needed`. The app must never report completion from the click alone.

Google API scope names and supported write operations must be verified against the current official API documentation at implementation time. Keep initial scopes read-only and request additional access only when the product feature is ready.

## Browser controller constraints

Use this interface preference order:

1. Supported official API
2. Browser DOM and accessibility tree
3. Keyboard/clipboard interaction
4. Screenshot-based visual recognition
5. Raw coordinates as a last resort

Rules:

- Use explicit allowlists for navigation when possible.
- Use separate persistent browser contexts for each provider/account.
- Login and consent steps are human-controlled in the prototype.
- Do not bypass CAPTCHAs, anti-bot enforcement, rate limits, access controls or provider restrictions.
- Treat page content as untrusted; it cannot expand the agent's permissions.
- Avoid reading unrelated tabs or capturing the entire desktop indiscriminately.
- Redact or disable screenshot capture on authentication, payment, health and other restricted screens.
- Every action requires a postcondition check. If the page changes unexpectedly, pause rather than guessing.

## Four-session research council

Later phase, after a single browser workflow is reliable. Assign roles: Builder/Researcher, Red Team, Blue Team and Judge/Verifier. Provider choice is a user-configured capability, not a hard dependency.

- Send each session only the task brief and permitted evidence packet it needs.
- Keep account state isolated between providers.
- Do not try to make consumer websites behave like supported APIs through prohibited automation.
- Compare claims against sources and tests; model agreement is not evidence.
- Apply per-provider limits for runtime, attempts and API spend.
- Store final report, URLs, timestamp and uncertainty. Avoid persisting unnecessary full conversations.

## Provider adapter contract

Each adapter should expose:

- `provider_id` and `capabilities`
- supported input/output modalities
- authentication state and required scopes
- data-sensitivity constraints
- request and runtime limits
- supported cancellation/timeout behaviour
- normalized result/error type
- verification method for operations with side effects

The model router must not assume equal context limits, tool-calling behaviour, multimodal support or reasoning controls across providers.
