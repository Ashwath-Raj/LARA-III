# Operations, Scheduling and Recovery

## Scope

This document owns the local runtime lifecycle and recovery behaviour. Security decisions remain defined by `04_SECURITY_PIPELINE.md`; the default permission matrix remains in `09_AUTONOMY_POLICY_MATRIX.md`.

## Local runtime layout

Keep mutable application data outside the source repository. Suggested Linux paths:

- Configuration: `${XDG_CONFIG_HOME:-~/.config}/ubuntu-agent/`
- Persistent state: `${XDG_DATA_HOME:-~/.local/share}/ubuntu-agent/`
- Cache: `${XDG_CACHE_HOME:-~/.cache}/ubuntu-agent/`
- Logs: `${XDG_STATE_HOME:-~/.local/state}/ubuntu-agent/` or a configured rotating log directory

Apply user-only permissions to sensitive directories. Never commit the database, OAuth tokens, browser profiles, screenshots, generated private reports or logs.

## Startup sequence

1. Load configuration and secret references; fail if required settings are invalid.
2. Acquire a single-instance lock or use a database-backed lease to prevent duplicate schedulers.
3. Open SQLite, enable foreign keys, run pending migrations and check database integrity where appropriate.
4. Initialize the policy engine. If policy cannot load, disable tool execution.
5. Connect to local providers only when configured; hosted providers stay disabled unless explicitly configured.
6. Reconcile reminders and notification events from persistent state.
7. Inspect non-terminal jobs and their in-flight steps. Resume only jobs whose state can be safely established.
8. Start the API/UI and background workers.
9. Emit a local health status showing ready, degraded or blocked dependencies.

An unavailable model must not prevent users from viewing or manually editing stored tasks. An unavailable database must prevent mutations and agent execution.

## Persistent reminders

The scheduler must be database-driven, not a collection of in-memory timers.

- Persist scheduled time, rule snapshot, channel and delivery state.
- On startup, find due reminders that were not delivered and classify them as `missed`, `due_now` or `expired` according to configured policy.
- Do not deliver duplicates after a restart. Use an atomic claim/lease and a unique delivery identifier.
- Recompute future reminders when task due dates or reminder rules change.
- Cancel stale reminders transactionally with the update that replaces them.
- Store delivery attempts and failure reasons.
- When the desktop session was asleep/offline, surface missed reminders after launch; do not imply a notification was delivered while the session was unavailable.

## Durable overnight jobs

Every job must persist:

- goal and expected deliverable
- permitted rooms, tools, providers and domains
- runtime and model/call/token/cost budgets
- retry caps, backoff and step timeouts
- checkpoint and current step
- approvals pending or consumed
- stop conditions and report location

After each meaningful step, save output references, verification status, audit event and checkpoint in a transaction. Do not store credentials or unrestricted private prompt history in checkpoints.

### Recovery rules

- **Crash before a tool call:** safely retry after checking the step state.
- **Crash during a read-only operation:** retry within the budget.
- **Crash during file modification:** inspect worktree, journal or checkpoint before retrying; never blindly apply the patch twice.
- **Crash during an external side effect:** treat the result as uncertain. Query the destination for evidence before any retry.
- **Expired approval:** return to `awaiting_approval`; do not execute.
- **Policy changed during interruption:** re-evaluate before resuming.
- **Provider/session expired:** pause for reauthentication; do not automate around consent.
- **Budget exhausted or repeated identical failure:** stop and report the blocker.
- **Global pause active:** dispatch no new tools; in-flight tools must be cancelled where supported and marked uncertain if cancellation cannot be confirmed.

## Pause and kill switch

Provide:

- Global pause: stop scheduling new work and stop new tool dispatches.
- Per-job pause/cancel: user can pause or cancel a selected job.
- Emergency stop: disable all tool execution, including background workers, until explicitly re-enabled by the user.
- Read-only safe mode: allow task viewing, report inspection and policy explanation while agent execution remains disabled.

The kill switch must be enforced in the executor/dispatcher, not merely by hiding UI buttons. UI and CLI should show whether work is running, paused or potentially in-flight. A kill request cannot guarantee that a remote action already accepted by a provider is reversible.

## Logs and observability

Use structured logs with timestamp, process/job ID, step ID, tool ID, policy decision, elapsed time and safe result code. Do not log raw secrets, cookies, OAuth tokens or full sensitive memory context. Redact filesystem paths or user content when they are not necessary for troubleshooting.

Keep the audit stream separate from noisy debug logs. Audit events record action, actor/persona, target reference, policy result, approval reference, result state and evidence reference. Limit modification access and define retention.

Track at least:

- ready/degraded dependency status
- pending/overdue reminders
- active, blocked and failed jobs
- retry counts and budget usage
- pending approvals
- provider timeouts/rate limits
- last successful backup and last database integrity check

## Backup and restore

- Back up SQLite with a consistent SQLite backup mechanism or coordinated checkpoint; do not blindly copy a live database file.
- Back up Qdrant/document artifacts with a documented consistent snapshot strategy, or provide a rebuild-from-source path.
- Encrypt backups when they contain personal data and store them outside the working tree.
- Preserve migrations and app version metadata with backups.
- Test restore into a temporary directory and validate schema, task counts, reminder state and vector/document references.
- Deletion requests must consider primary storage, chunks, vectors, caches, generated reports and backups according to the retention policy.

## Optional user-level service

After foreground execution works reliably, provide an optional `systemd --user` service for the scheduler/API. It should run as the unprivileged desktop user, use explicit environment/configuration, restart on failure with backoff, and not require enabling a root service. Desktop notifications may require a logged-in graphical session; report this limitation rather than claiming notifications are always available.

## Operational readiness checklist

- Startup with a missing local model remains usable for manual task management.
- Restart recovers reminders without duplicate delivery.
- Interrupted jobs resume only after step state and policy are revalidated.
- A timed-out submission is checked before retry.
- Pause/kill disables new tool dispatch even if the UI is closed.
- Logs do not contain credentials or restricted raw prompts.
- Backup restore passes a test before a release.
