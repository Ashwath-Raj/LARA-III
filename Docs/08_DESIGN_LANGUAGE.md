# Ubuntu Agent — UI/UX Design Language

**Working name:** Ash / Ubuntu Agent  
**Design intent:** a calm, capable desktop workspace with the personality of a well-made instrument: smoky ash surfaces, warm paper, precise typography, and restrained electric-blue activity. It should feel alive without performing “AI magic” for attention.

---

## 1. Product feel

### The visual idea

Build a **smoky, editorial workspace** rather than a generic chatbot dashboard. The interface borrows the conversational familiarity of ChatGPT—persistent left navigation, a central conversation, a composer anchored near the bottom—but gives it a more tactile, considered identity:

- **Ash for the environment:** the application frame and work surfaces sit in soft grey rather than pure white.
- **Paper for thought:** chat responses, notes, reports, and source excerpts use a clean white surface.
- **Warmth without decoration:** the beige tone softens the technical parts of the product.
- **Cerulean for intent and activity:** links, selected graph paths, focus, live execution, and primary actions use the blue accent sparingly.
- **Strong type, light structure:** use typographic hierarchy and spacing instead of drawing a border around every element.
- **Visible work:** show what the agent is researching, waiting for, executing, or verifying. Do not simulate intelligence with random animation.

### Personality

- Quietly competent, not chirpy.
- Dense enough for a technical user, but never cramped.
- Honest about uncertainty, permissions, and task state.
- Small moments of responsiveness; no constant motion.
- Desktop-native in spirit, web-quality in execution.

### Design principles

1. **Content before chrome.** Reports, assignments, notes and evidence get the visual priority.
2. **One strong accent.** Cerulean signals action or meaningful activity; it is not a decoration colour for every icon.
3. **Surface hierarchy over borders.** Use shifts in background, spacing and typography before adding outlines.
4. **Motion communicates state.** Every animation must indicate progress, focus, change, or completion.
5. **Reveal complexity progressively.** The default view is calm; graph topology, tool traces, model details and audit records appear when opened.
6. **Autonomy must be legible.** The user can see what is running, what it can access, what it has done, and what it needs permission to do.

---

## 2. Colour system

Use the five supplied palette colours as the canonical brand system. Do not introduce a second competing accent palette.

| Token | Hex | Role | Usage |
|---|---|---|---|
| `onyx` | `#121619` | Deep ink | Primary text on light surfaces, sidebar in dark mode, strong contrast, terminal-like metadata |
| `beige` | `#E3E7D3` | Warm neutral | Selected navigation tint, note paper, gentle section backgrounds, personal workspace warmth |
| `silver` | `#BDC2BF` | Ash midtone | Secondary panels, graph canvas base, dividers when needed, disabled or inactive structure |
| `grey-olive` | `#989C94` | Muted structure | Secondary text, quiet controls, timestamps, inactive graph nodes and subtle framing |
| `cerulean` | `#0075A2` | Active signal | Primary action, keyboard focus, selected graph paths, actionable links, live execution indicator |

### Semantic tokens — light / ash theme

| Semantic token | Value | Intended use |
|---|---|---|
| `--app-canvas` | `#E9EBE7` | Global smoky-ash background; a softened surface derived from the palette |
| `--surface-primary` | `#FFFFFF` | Conversation transcript, report body, main editor |
| `--surface-secondary` | `#BDC2BF` at low visual weight | Side panels and secondary work areas; avoid making the whole app look flat grey |
| `--surface-warm` | `#E3E7D3` | Sticky notes, selected items, warm section highlights |
| `--text-primary` | `#121619` | Main readable content |
| `--text-secondary` | `#555B56` | Supporting copy; use a tested contrast-safe value derived toward Onyx rather than placing small text in `#989C94` on white |
| `--text-muted` | `#666C66` | Timestamps, hints, metadata; do not use for essential instructions at small sizes without contrast testing |
| `--border-subtle` | `rgba(18, 22, 25, 0.10)` | Rare separators and input boundaries |
| `--accent` | `#0075A2` | Primary interactive accent |
| `--accent-soft` | `rgba(0, 117, 162, 0.10)` | Selected state background, focus halo background, active tool chip |
| `--accent-glow` | `rgba(0, 117, 162, 0.24)` | Very restrained graph glow or live activity highlight |
| `--danger` | `#121619` + explicit warning text/icon | Avoid inventing a saturated alarm palette; destructive actions need a clear label, icon, and confirmation surface |

**Contrast rule:** the palette's `#989C94` and `#BDC2BF` are not automatically safe for small text on white. Use them as surfaces, large labels, icons or structural colour unless a contrast check confirms readability. The product must meet WCAG AA contrast for ordinary text and visible keyboard focus.

### Colour behaviour

- The **chat response surface stays white**. The app frame around it carries the smoky ash tone.
- Keep `#121619` as the main text colour, not pure black in every possible context.
- Use beige to distinguish notes and selected warm areas, not as a full-screen wash.
- Use Cerulean for one primary action per view where practical. Secondary buttons stay quiet.
- Graph glow is created with low-opacity Cerulean, not gradients across the whole screen.
- Status also uses text and iconography; never rely on colour alone.

### Optional low-light theme

Offer a deliberate “Night Ash” mode after the light theme is stable. Use Onyx as the main canvas, lightly lifted charcoal surfaces, white text, Beige for selected warm surfaces, and Cerulean for active signals. Do not invert every colour mechanically: notes and approval dialogs must preserve readable contrast and clear surface hierarchy.

---

## 3. Typography: character through weight, not decoration

The interface should have **a distinctive, editorial type system**: high readability for long work, expressive weight changes for hierarchy, and monospaced detail where precision matters.

### Recommended font roles

- **Interface and conversation:** `Geist Sans` (preferred) or `Inter` as a robust fallback. Clean, slightly technical, readable at compact desktop sizes.
- **Technical metadata:** `Geist Mono` or `IBM Plex Mono` for timestamps, model IDs, run IDs, commands, graph relation names, latency and token/cost data.
- **Editorial accent:** `Newsreader` used sparingly for report titles or a featured research finding—not for navigation, forms, or dense body text. This adds a little human warmth without turning the product into a magazine.

Host fonts locally where licensing and distribution allow, and retain system fallbacks. Do not make the app depend on a network font request at startup.

### Type scale

| Token | Size / line height | Weight | Use |
|---|---|---|---|
| `display` | 32 / 38 px | 650–700 | Rare page title or first-run welcome |
| `h1` | 26 / 32 px | 650–700 | Main workspace title |
| `h2` | 20 / 27 px | 600–650 | Section and report headings |
| `h3` | 16 / 23 px | 600 | Panel headings, task groups |
| `body` | 15 / 24 px | 400–450 | Primary conversation and note content |
| `body-strong` | 15 / 24 px | 600–650 | Emphasis within a paragraph |
| `label` | 13 / 18 px | 550–600 | Controls, navigation items, field labels |
| `meta` | 11–12 / 16 px | 450–500 | Timestamps and supporting metadata; keep nonessential |
| `code` | 12–13 / 19 px | 400–500 | Commands, paths, IDs and technical output |

### Weight and emphasis rules

- Use strong weight for meaning: task titles, decisions, key numbers and the beginning of a scan path.
- Avoid making whole paragraphs bold. A user should be able to scan bold items and understand the structure.
- Avoid all-caps labels except tiny technical tags such as `LIVE` or `READ ONLY`; letter spacing should be subtle.
- Do not use ultralight fonts for body text or oversized bold text for every heading.
- Use italics mainly for quotations or uncertainty notes, not for routine UI labels.

---

## 4. Layout and navigation

### Desktop shell

Use a three-part workspace:

1. **Left navigation rail / collapsible sidebar** — rooms, personas, inbox, tasks, graph, active runs and recent work.
2. **Central workspace** — chat, task board, report, browser-research review or graph view.
3. **Context drawer** — optional right-side evidence, task details, source list, permissions or run trace. It opens when useful and can be dismissed.

Suggested desktop measurements:

- Expanded left sidebar: `248–272 px`.
- Collapsed rail: `60–72 px`.
- Main content reading width: `720–900 px` for conversation and reports.
- Optional context drawer: `300–360 px`.
- Standard page gutters: `24–32 px`.
- Compact panel gaps: `8–12 px`; section gaps: `20–28 px`.

The main canvas should not be enclosed in a stack of cards. Keep the composition spacious and let the central work area dominate.

### Left sidebar behaviour

- Persistent, quiet and collapsible—similar in familiarity to ChatGPT, but with more visible task and room navigation.
- The top area contains the product mark and a clear `New task` action.
- Core navigation: **Inbox, Today, Projects, Calendar, Knowledge Graph, Personas, Runs / Reports**.
- Room navigation is grouped separately and visually marked with a small room icon and sensitivity indicator.
- Recent conversations and active runs appear below the primary navigation.
- The sidebar can show a narrow progress tick or dot for active jobs, not an animated spinner on every item.
- Hover reveals secondary actions. Keyboard focus exposes the same actions without a mouse.
- On narrow windows, collapse to an icon rail and provide an explicit way to return to full navigation.

### Border philosophy

- Do not border every panel, button, or chat message.
- Prefer surface contrast, alignment and spacing.
- Use a one-pixel low-opacity divider when two areas truly need separation.
- Use a visible outline for keyboard focus and risky approval controls; “no borders” must not mean invisible focus or ambiguous hit targets.
- Shadows should be soft and local. Avoid floating-card shadows on every element.

---

## 5. Chat workspace

### Conversation surface

- The conversation content sits on **white** against the surrounding smoky canvas.
- Avoid putting every message in a rounded bubble. Assistant output should read like a document; user prompts can use a subtle warm-grey or beige-tinted block where separation is needed.
- The agent's answer uses clear heading levels, short paragraphs, citations and structured code blocks.
- Tool traces are collapsed by default but easy to expand: `Searched 4 sources`, `Read 3 files`, `Waiting for approval`, `Verified 6 checks`.
- Show the chosen model as quiet metadata, e.g. `Gemma · Local` or `Gemma · Cloud`, alongside a data-routing indicator when it matters.
- Citations open a source drawer with the original URL, extracted passage, fetch time and source type.
- In-progress work shows a concrete verb and stage—`Searching sources`, `Comparing claims`, `Running tests`—instead of “thinking…” for an indefinite period.

### Composer

- A persistent bottom composer with generous inner padding, a soft surface contrast and a restrained radius.
- Placeholder copy should invite outcomes, not just questions: `What should I move forward?`
- Support attachments, room/context selection, model route visibility, voice input only if implemented, and a clear send/stop control.
- The current privacy route should be visible when external processing may happen: `Local only` / `Cloud allowed`.
- Tool permissions are visible before consequential execution, not buried in settings.
- Enter sends only when the interaction makes that behaviour clear; Shift+Enter creates a newline.
- While a long run is active, change the primary control from Send to a clearly labelled Stop/Pause affordance.

### Conversation tone

Write like a capable technical collaborator: concise, specific and transparent. Avoid fake enthusiasm, excessive emojis, anthropomorphic claims, and statements such as “I am thinking deeply” when a concrete run state can be shown.

---

## 6. Personal tracker: Inbox, Kanban, sticky notes and deadlines

This is a core productivity area, not an auxiliary dashboard.

### Inbox

- The Inbox is a low-friction capture space for natural-language tasks, sticky notes, pasted text, links and assignment details.
- Cards can be rapidly triaged into `Today`, `Upcoming`, a project, a room, or an archive.
- Use narrow category accents and labels rather than painting every category a different bright colour.
- A small AI-assist action can extract title, subject/course, deadline, expected deliverable, source and next action. The extracted result remains editable before saving.

### Kanban board

Default columns:

- **Inbox** — untriaged captures.
- **Next** — clear next actions.
- **In progress** — work currently underway.
- **Waiting** — blocked by a person, resource or external event.
- **Done** — completed items with a completion record.

Use drag-and-drop, but provide keyboard and menu alternatives. Moving a task between columns must be a user-visible, undoable operation. Do not turn each card into a dense mini-dashboard.

### Sticky-note language

- Use Beige `#E3E7D3` for notes that should feel tangible and personal.
- Use White for standard task cards; use smoky grey for metadata and grouped regions.
- Use a small Cerulean edge, dot or left marker for selected/high-priority notes. Never fill every note with Cerulean.
- Keep the note's title, next action and due date visible. Secondary details appear on open.
- Random rotation is discouraged; if ever used, keep it extremely subtle and never rotate cards containing dense text.

### Natural-language deadline capture

Example request:

> “I have Assignment X for Data Structures due on the 7th. Remind me to finish the solution, save it as `assignment_x.pdf`, and submit it to Google Classroom.”

The system should:

1. Parse the task title, subject/course, due date, time if supplied, required file, destination and requested reminder cadence.
2. Resolve ambiguous dates before scheduling. If month, year or timezone is unclear, ask a concise clarifying question rather than silently choosing.
3. Create the task and its deadline in Operations, with only the minimum necessary course/project metadata bridged from Academic.
4. Propose a reminder plan with editable defaults—for example, an early heads-up, a day-before reminder and a due-day reminder. Do not create duplicate reminders if the task is edited.
5. Track task status and completion evidence. The date being parsed is not proof that the assignment has been completed.
6. Keep the final submission as a distinct approval-gated action.

### Reminder system

- Persist reminders in the local database; do not rely only on an open browser tab or in-memory timer.
- Support OS desktop notifications, quiet hours, snooze, escalation rules and a notification queue.
- Notify on meaningful events: deadline approaching, task overdue, submission approval required, upload result confirmed, or a workflow blocked.
- Offer a concise notification with one primary action, e.g. `Review submission` or `Snooze 30 min`.
- Keep notification history accessible from Inbox/Today.
- Do not send noisy messages for every model step. Overnight jobs report milestones and exceptions, not every turn.
- If the device is asleep or powered off, show the missed reminder on the next launch. Do not claim reminders are guaranteed while the OS is unavailable.

### Google Classroom submission policy

The agent can prepare and stage the submission flow, but it must distinguish three states: **prepared**, **submitted**, and **submission verified**.

- Read the course and assignment details through the approved integration where available.
- Check that the course, assignment, file path and target attachment match the user's intent.
- Validate that the file exists, opens and has the expected name/type. Display the target course and assignment to the user.
- Uploading a file may be allowed under a preapproved narrow policy, but **final submission/turn-in requires explicit approval** by default.
- The approval is bound to the exact course, assignment, attachment and action. If any of those change, request approval again.
- After execution, verify success through an authoritative result from the API or page state. Save the confirmation and timestamp.
- If the response is uncertain, report `submission status unknown` and ask the user to check—never claim success based on a click alone.
- Never fabricate a completion state, alter submitted work to conceal authorship, or bypass institutional restrictions.

---

## 7. Knowledge graph: neon, but disciplined

The graph is the product's most visually distinctive surface. It should feel like a **living map of knowledge**, not a cyberpunk wallpaper or glowing ball of nodes.

### Graph appearance

- Canvas: softly smoky grey with a subtle paper-like texture only if it does not reduce clarity.
- Nodes: solid, quiet shapes; colour indicates room or entity type only where useful.
- Edges: fine neutral lines by default; relationship labels appear on hover, selection or at high zoom.
- Active path: Cerulean edge with a restrained outer glow. The glow should be visible on a selected path, not across the entire graph.
- Selected node: sharp Cerulean indicator ring and clear label; avoid neon fill that makes text hard to read.
- Related nodes: brighten gently when the user selects a node. Unrelated nodes recede through opacity rather than disappearing without explanation.
- Cluster labels: small, legible labels for Academic, Projects, Operations, Personal, Health and Public Research—subject to access permissions.
- Layout: favour stable spatial arrangements where possible. Avoid nodes constantly drifting, bouncing or reflowing while the user tries to read.

### Graph interaction

- Hover shows a compact preview: name, type, source count, last updated and access label.
- Click opens a detail drawer instead of forcing a full-page navigation.
- Double click or an explicit action opens the node's document/task/project.
- Filters for room, entity type, date range, confidence and source.
- Search supports both entity names and semantic discovery.
- A `Why is this connected?` action displays the relationship path and source evidence.
- A `Trace information flow` view shows cross-room bridges and which fields were shared.
- Graph exploration must not reveal the name or existence of restricted nodes to users/personas who cannot access them; even metadata can be sensitive.

### What “neon” means here

Use a Cerulean halo at low opacity, crisp node edges, short selection transitions and a subtle activity pulse on the current operation. No rainbow node clouds, purple-blue gradients, constantly moving particles, 3D starfields, or decorative neural-network backgrounds. The graph should remain readable in a screenshot or printed report.

---

## 8. Rooms, personas and trust indicators

The user must know **which context is active** and what it can access.

- Show the current room near the workspace title or composer: `Academic`, `Projects`, `Public Research`, etc.
- Use an understated lock icon and a readable label such as `Restricted` or `Local-only`; do not rely on a tiny padlock alone.
- Show persona as a functional mode, not a mascot: `Exam Coach`, `AI/ML Researcher`, `Desktop Operator`.
- Each persona can have a small distinct glyph, but personas should share the same design system.
- A cross-room bridge is visible in the activity trace and includes source, destination, fields and purpose.
- When cloud routing is enabled, display it clearly and name the provider. If the policy blocks cloud use, tell the user why in plain language.
- Permission denials should be calm and actionable: `This task can read Academic but cannot access Health. Change policy or keep the contexts separate.`
- Avoid “military UI” visual clichés. The access model should be rigorous; the interface should remain humane and usable.

---

## 9. Live execution, autonomy and approvals

The application should feel live because state is observable.

### Run status language

Use a consistent run lifecycle:

`Queued → Planning → Researching → Reviewing → Ready for approval → Executing → Verifying → Completed`

Alternative terminal states: `Paused`, `Blocked`, `Failed`, `Cancelled`, `Needs attention`.

- The active stage gets a tiny Cerulean indicator and a clear verb.
- Completed stages become quiet checkmarks and timestamps.
- A progress bar is appropriate when the total work is bounded and progress can be estimated honestly. Otherwise show the current stage and completed checkpoints.
- Do not show fake percentages for open-ended model reasoning.
- Offer `Pause`, `Stop`, and `Inspect run` as stable controls for a long job.

### Approval surfaces

Approval dialogs should be unusually clear. They show:

- The action to be taken, in plain language.
- Exact target/resource and relevant arguments.
- Why it is needed and which policy allowed the proposal.
- What data leaves the machine, if any.
- Whether the action is reversible.
- The precise approval scope and expiry.

For commands, show the full command and working directory. For file edits, show a diff. For Classroom, show course, assignment and attachment. Approving one action must not grant blanket permission for future actions.

### Notifications

- Use native Ubuntu desktop notifications for brief alerts and a persistent local Inbox for history.
- Completion notification: one-line outcome, plus `Open report`.
- Approval notification: action and risk category, plus `Review`—never an ambiguous one-click approval for a high-risk action.
- Blocker notification: what stopped, what has already been done, and the next available choice.
- Respect quiet hours. Critical deadline or security events can be configured separately, not silently exempted by default.

---

## 10. Reports and research-council output

Research reports are long-form working documents, not chat bubbles.

- White document surface on an ash workspace.
- Title, generated time, task objective, status and model/provider metadata in a compact header.
- Executive summary first, evidence and comparison next, recommendation and open questions last.
- Sources appear inline and in a source list with original URLs and access timestamps.
- Separate `Observed`, `Inferred`, `Recommendation` and `Unverified` where the distinction matters.
- Red-team challenges, blue-team mitigations and judge decisions appear as traceable sections, not theatrical avatars arguing in bubbles.
- Provide `Copy summary`, `Open sources`, `View run trace`, `Export Markdown` and `Save to room` actions.
- Never present multiple model opinions as verified facts merely because they agree.

---

## 11. Component styling

### Buttons

- **Primary:** Cerulean fill, white text, readable label; use for the principal action only.
- **Secondary:** transparent or quiet surface with Onyx text; no heavy outline unless necessary for clarity.
- **Tertiary:** text action with hover/focus treatment.
- **Dangerous:** clear verb such as `Delete permanently`, visible target and confirmation; do not use a vague `OK` button.
- Minimum interactive target: aim for `40–44 px` height where space allows.

### Inputs and search

- Inputs use a light surface difference and a subtle boundary only when needed.
- Focus state gets a clearly visible Cerulean ring; it must not depend only on a colour change of one pixel.
- Search results display why they matched and which room/source they came from, if allowed.
- Empty states should suggest a single useful next step rather than fill space with illustrations.

### Tags and status

- Keep tags sparse. Prefer one status and one context label over a pile of badges.
- Use subdued fills; reserve Cerulean for the currently active or actionable item.
- Do not create a different colour for every persona, model, project or task status.

### Icons

- Use a consistent thin-to-regular stroke icon family, e.g. Lucide.
- Icons support labels, not replace them for unfamiliar or risky actions.
- Do not use random emoji as product iconography. A limited expressive symbol may be used in user-authored notes, not as the entire visual language.

### Corners and elevation

- Main panels: `12–16 px` radius.
- Inputs and small controls: `8–12 px` radius.
- Small chips: use a restrained radius; not every element needs a pill shape.
- One soft elevation level for overlays/popovers; avoid stacked floating cards.

---

## 12. Motion and micro-interactions

Animation should add perceived responsiveness and reveal causality.

- Sidebar collapse: `160–220 ms` with a smooth width/opacity transition.
- Drawer open/close: `180–240 ms`, directional and restrained.
- Button press: brief change in scale or surface value; no springy overshoot.
- Graph focus: `180–300 ms` to reveal neighbours and highlight a path.
- Task move: optimistic movement with an immediate Undo action; confirm persisted state.
- Live execution: a gentle pulse every few seconds on the one active indicator. No continuous whole-screen movement.
- New result: subtle fade/slide, not a confetti burst.
- Loading: skeleton only when layout is known; otherwise a compact status line.
- Respect `prefers-reduced-motion`. All essential meaning must remain when animation is disabled.

The interface can feel alive through fresh status updates, changing graph focus, cursor/selection response, notification transitions, and clear run progress. It does not need a fake animated orb or constant shimmer.

---

## 13. Accessibility and keyboard use

- Support full keyboard navigation, visible focus and escape-to-close for drawers/dialogs.
- Provide accessible names for icon-only controls and announce important run-status changes to assistive technology without announcing every token or intermediate thought.
- Use headings semantically; body text should remain at a comfortable reading size.
- Meet WCAG AA contrast for text and interactive states.
- Do not encode room sensitivity, status or graph type in colour alone; combine colour with labels, patterns, icons or text.
- Offer a reduced-motion mode and a way to disable periodic screenshots.
- Make Kanban actions accessible through menus/keyboard as well as drag-and-drop.
- Keep click targets comfortably sized and prevent hover-only actions from being inaccessible on touch or keyboard.

---

## 14. Data visibility and privacy in the UI

- Always show which room and persona are active when the user is about to search, share, or execute something.
- Make the local/cloud route visible for tasks that may send data externally.
- Before external processing, show a concise disclosure of the context categories to be sent—not a confusing dump of every memory record.
- Separate screenshots, browser state, OAuth tokens and application memory. They have different sensitivity and retention requirements.
- Pause or mask screen capture on authentication, credential, health and other restricted screens.
- Make audit records readable: action, actor/persona, policy decision, approval, target, timestamp and result.
- Provide clear controls for deleting a memory, removing a cross-room bridge and clearing retained screenshots.

---

## 15. Anti-patterns: things this product must not look like

Avoid the familiar “AI-generated SaaS dashboard” look:

- Purple/blue gradient backgrounds and glows on every surface.
- A giant glowing orb used as a substitute for meaningful status.
- Glassmorphism on every card, excess blur or transparent floating panels everywhere.
- Rounded cards nested inside rounded cards inside another rounded card.
- A badge for every noun and a different saturated colour for every status.
- Emoji-heavy navigation, robot mascots, decorative sparkles and generic “magic AI” copy.
- Fake real-time activity, fake progress percentages, or an endless “thinking” animation.
- Dense, always-visible tool logs that drown out the actual answer.
- A graph that is visually exciting but too bright to read or impossible to navigate.
- A personal tracker that is just a row of metrics rather than a useful capture-and-action system.
- A security interface that looks intimidating but hides the actual permission decision.

If an element does not improve reading, orientation, confidence, or action, remove it.

---

## 16. Example design tokens

A starting CSS token set for implementation:

```css
:root {
  color-scheme: light;

  --onyx: #121619;
  --beige: #E3E7D3;
  --silver: #BDC2BF;
  --grey-olive: #989C94;
  --cerulean: #0075A2;

  --app-canvas: #E9EBE7;
  --surface-primary: #FFFFFF;
  --surface-warm: var(--beige);
  --text-primary: var(--onyx);
  --text-secondary: #555B56;
  --text-muted: #666C66;
  --border-subtle: rgba(18, 22, 25, 0.10);
  --accent: var(--cerulean);
  --accent-soft: rgba(0, 117, 162, 0.10);
  --accent-glow: rgba(0, 117, 162, 0.24);

  --font-ui: "Geist Sans", "Inter", system-ui, sans-serif;
  --font-mono: "Geist Mono", "IBM Plex Mono", ui-monospace, monospace;
  --font-editorial: "Newsreader", Georgia, serif;

  --radius-control: 10px;
  --radius-panel: 14px;
  --radius-overlay: 16px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;

  --motion-fast: 160ms;
  --motion-normal: 220ms;
  --motion-slow: 300ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}

/* Use only for a selected/current graph path—not as a general card effect. */
.graph-edge--active {
  stroke: var(--cerulean);
  filter: drop-shadow(0 0 3px var(--accent-glow));
}

:focus-visible {
  outline: 2px solid var(--cerulean);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

These are starting tokens, not a substitute for testing real screens. Check actual contrast, line length, focus visibility and scaling in the implementation.

---

## 17. First screens to design

Build and validate these in order:

1. **Home / Inbox:** quick capture, Today, upcoming deadlines, active overnight run and recent notes.
2. **Chat / Agent workspace:** white transcript on ash canvas, composer, visible room/model route and expandable tool trace.
3. **Task detail:** course/project, deadline, reminders, expected files, approval status and submission evidence.
4. **Kanban:** Inbox, Next, In progress, Waiting, Done; drag-and-drop plus accessible alternatives.
5. **Knowledge Graph:** search, filters, selected node, relationship evidence and cross-room flow explanation.
6. **Run report:** executive summary, claims and sources, red-team findings, verification status and next actions.
7. **Approval centre:** exact proposed action, policy basis, scope, data disclosure, diff/target and approve/reject controls.

Do not design the graph, agent council and four-browser desktop view before the inbox/deadline/chat loop is coherent. The product's everyday value comes from capturing work and reliably moving it forward.

---

## Final design test

Before accepting a screen, ask:

- Does the eye land on the work rather than decoration?
- Is the app recognizably smoky ash, warm beige, silver-grey and Cerulean without using every colour everywhere?
- Does typography create hierarchy without making every element bold?
- Can the user tell what the agent is doing, what it can access and what happens next?
- Does the graph look alive only where something is active, while remaining calm elsewhere?
- Can the task be completed with a keyboard and can the interface be used with reduced motion?
- Does any glow, card, animation or badge convey useful information? If not, remove it.

**North star:** *smoky, tactile, intelligent, legible, quietly alive.* A workspace with enough soul to invite use and enough restraint to stay useful for hours.
