# LARA IV — conversational workspace

## Product direction

LARA IV opens on Ask LARA, a focused conversational workspace with an authored breathing waveform, a compact composer, useful prompt starters, and a disclosed mock tool catalog. The waveform is a signature for the workspace, not a claim that inference is running. The typed mock adapter stores chronological messages by stable conversation identity in browser storage and returns a static simulation reply. Saved conversations are selected in a separate history dialog; no recent-response preview duplicates transcript messages.

## Information architecture

- Daily navigation: Ask LARA, Today, Inbox, Kanban, Calendar, Reminders.
- Secondary navigation is grouped and collapsible: Projects & Memory, Operations & Governance, System & Settings.
- Room switching is contextual and compact; its panel contains the full room catalog and sensitivity context.
- Persona choice is visible but explicitly does not change authorization.
- Desktop navigation collapses; mobile navigation opens as a labeled drawer.

## Visual and interaction system

Retain the product specification's ash workspace, paper surfaces, restrained cerulean focus, system font stack, 4px spacing base, and readable contrast. Ask LARA uses a muted mineral green-grey waveform built from layered SVG curves. Idle breath is slow, focus adds definition, processing uses a modestly quicker rhythm, response returns to rest, and errors use quiet text feedback. Reduced-motion preferences render a static wave.

The composer supports Enter to send and Shift+Enter for a new line. A preview names the likely simulated operation before sending. Every conversation response is marked simulated; no model or tool executes. Provider connections remain unavailable in the prototype.

The original transparent `logo.png` appears during a brief once-per-launch transition. The SVG wave breathes slowly, responds locally to pointer movement and composer focus, and freezes to a composed static form when reduced motion is requested.

The knowledge graph uses a lazy-loaded 3D force renderer plus accessible node and relationship lists. Its adapter accepts only explicitly linked bundled prototype nodes and edges, marks their source as prototype data, redacts local path/hash metadata, and does not claim persistent or authorized backend provenance. A trusted graph endpoint is still required for live records.

## Reference traits

- Linear: keep attention work scannable and preserve a useful path into item details.
- Things: use calm date hierarchy on Today.
- Obsidian: keep graph exploration scoped and selectable.
- GNOME HIG: support keyboard navigation and adapt navigation to viewport size.

References inform interaction principles only. LARA IV does not copy another product's branding or shell.

## Review criteria

- At first glance, Ask LARA is the main interaction and simulation mode is clear.
- Daily routes are easy to reach; secondary routes and room inventory do not dominate.
- Long task names, no-results states, larger boards, dialogs, reduced motion, and narrow screens remain usable.
- Useful mock workflows and browser persistence remain available.
- Never claim an external action, provider call, or live inference without verified integration.
