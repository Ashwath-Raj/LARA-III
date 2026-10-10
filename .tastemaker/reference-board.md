# Reference board

Created: 2026-10-11
Mode: Operate
Design read: a local-first student productivity workspace for a student operator; operate mode, smoky field-notes lane, variance 4 / motion 2 / density 7 / art direction 6.
Sourcing: official product documentation fetched and read on 2026-10-11. Reference pages were inspected as text; their live screenshots were not captured.

## Quality bar

- [Linear Inbox](https://linear.app/docs/inbox): its priority view separates attention-worthy items from the rest, and opening an item preserves the ability to act on it. Borrow that focus and contextual inspection pattern for the task queue.
- [Linear board layout](https://linear.app/docs/board-layout): status lanes stay scannable while view and ordering controls are explicit. Borrow the three-workflow-lane density and keep the keyboard/menu alternative available.
- [Linear filters](https://linear.app/docs/filters): filters narrow the current view and update it immediately. Borrow the live-filter behavior and a useful no-match state.
- [Things](https://culturedcode.com/things/): the official overview centers a day plan and keeps task organization quiet. Borrow deadline grouping and a readable date hierarchy, not its platform-specific shell.
- [Obsidian Graph view](https://obsidian.md/help/plugins/graph): hover/click reveals local relationships, and filters constrain what appears. Borrow selectable nodes and scoped exploration, not a decorative whole-vault map.
- [GNOME HIG navigation](https://developer.gnome.org/hig/guidelines/navigation.html): flat views suit frequent switching; sidebars suit larger view counts; keep one clear focus per view. Borrow an adaptive, shallow navigation model.
- [GNOME HIG accessibility](https://developer.gnome.org/hig/guidelines/accessibility.html): keyboard access is a first-class interaction path. Borrow the emphasis on accessible controls and keyboard reachability.
- [Ubuntu Agent UI specification](../Docs/08_DESIGN_LANGUAGE.md): the product's canonical ash, beige, silver-grey, and cerulean system; simulation honesty; room awareness; and reduced-motion rules are the source of truth for product identity.

## Borrow

- **Palette/material:** Ubuntu Agent specification → keep ash canvas and beige capture paper; use cerulean only for focus/actions. Pair each status color with text.
- **Type/hierarchy:** Things day-planning and Linear item rows → a small editorial date/title accent above compact, legible task metadata.
- **Layout/composition:** GNOME navigation plus Linear's queue/board → preserve the existing shell, prioritize Today/Inbox, and use compact domain-specific surfaces rather than metric-card grids.
- **Motion/interaction:** GNOME keyboard guidance and Obsidian graph controls → selection, visible focus, and state feedback. The only ambient motion is the user-requested Ask LARA wave; it responds to local pointer/focus state and becomes static with reduced motion.
- **Asset language:** existing Lucide icon dependency → consistent named action icons; no decorative imagery or emoji-led navigation.

## Avoid

- Generic analytics dashboards, giant statistics, glass surfaces, colorful status clouds, decorative graph networks, and unlabeled icon controls.
- Copying another product's branding, palette, sidebar layout, or exact interaction taxonomy.
- Imagined reference measurements. The color values are inherited from Ubuntu Agent's canonical design spec and are independently contrast-checked.

## Direction contract

- **Thesis:** a calm, tactile work surface that makes the next student task and its permission context easy to see.
- **First viewport:** Ask LARA with the breathing-wave identity, focused composer, honest simulation note, prompt starters, and expandable mock tools. Daily commitments stay in their dedicated workspaces.
- **System:** product ash/beige/cerulean tokens, system sans UI text, sparse Georgia date/title accent, 4px spacing base, 8–14px corner range, and sub-250ms state feedback with reduced-motion support. Ask LARA adds a low-saturation mineral waveform, with reduced motion showing a static form.
- **Risk:** too much of the existing inline-styled prototype could dilute the visual language; normalize the shared CSS treatment without removing useful routes or data behaviors.
