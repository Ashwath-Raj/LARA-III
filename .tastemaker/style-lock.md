# Style lock — LARA IV

Established: 2026-10-11. Source: product `Docs/08_DESIGN_LANGUAGE.md`, the LARA IV redesign brief, and fetched Linear, Things, Obsidian, and GNOME HIG references. Reference traits were synthesized; no reference brand or layout is copied.

## Palette

- Background: `#E9EBE7` (workspace canvas)
- Surface: `#FFFFFF` (task/list surfaces)
- Warm surface: `#E3E7D3` (capture paper and focused date)
- Primary: `#0075A2` (primary action; white label)
- Accent text: `#005779` (links, quiet action text, selected graph details)
- Text primary: `#121619` — contrast vs canvas `15.16:1`, AA pass
- Text secondary: `#474E49` — contrast vs canvas `7.13:1`, AA pass
- Text muted: `#626861` — contrast vs canvas `4.77:1`, warm paper `4.53:1`, AA pass. Darkened from the spec starter `#666C66` because the starter measured `4.49:1` on canvas.
- Status: danger `#B52B27`, warning `#996200`, success `#1D7337`; pair each with a text label.
- Button label color: white — contrast vs Primary `5.16:1` (dark text is only `3.52:1`, so do not use it on the primary fill).
- Dark mode: not needed for this prototype; single light mode only.

Contrast measurements from `.agents/skills/tastemaker/scripts/check_contrast.py` on 2026-10-11. Body text/background and primary button label/fill pass WCAG AA. Status text on white surfaces: danger `6.29:1`, warning `5.12:1`, success `5.90:1`.

### Color contract

- Text-safe combinations: ink/canvas `15.16:1`; secondary/canvas `7.13:1`; muted/canvas `4.77:1`; muted/warm `4.53:1`; white/primary `5.16:1`; accent-text/canvas `6.63:1`; danger/white `6.29:1`; warning/white `5.12:1`; success/white `5.90:1`.
- UI-safe combinations: primary/canvas `4.30:1`, warning/canvas `4.27:1` (icons, large text, and state edges only; never body text).
- Decorative only: canvas/surface `1.20:1`, canvas/warm `1.05:1`, surface/warm `1.26:1`; use for subtle surface separation only, never as the sole state signal.
- Primary buttons always use white text. Accent links use `#005779`, not `#0075A2`.

## Typography

- UI: Ubuntu / system sans fallback. No remote font request.
- Display accent: Georgia, used only for the Today greeting and date-forward title.
- Monospace: Ubuntu Mono / system monospace for dates and technical state.
- Body 14px; secondary copy 11–12px; workspace titles 20–36px fluid; numbers use tabular figures where aligned.

## Shape language

- Controls: 8px radius; task rows/cards: 8–12px; major panels: 12–14px.
- One restrained shadow level. Borders mark group boundaries and focus, not every nested surface.
- Spacing follows 4px base: 8, 12, 16, 20, 24, 32px.

## Motion

- Other screens use state changes only: named colors/background/border/transform transitions, generally 120–220ms.
- Drag keeps the user's item under the pointer and highlights the active drop lane.
- `prefers-reduced-motion` removes spatial movement and reduces transitions to near-instant.

### Ask LARA identity exception

Ask LARA uses the unchanged transparent `logo.png` on the Onyx `#121619` startup canvas so the logo's white wordmark remains legible. It transitions once per launch into the light workspace and product-specific layered SVG wave. The wave breathes slowly and deforms locally around a fine pointer; focus adds definition, an explicitly simulated pending save may shorten its rhythm, response settles, and errors stay textual and calm. Reduced motion shows the same static wave and an immediate logo state. Wave colors are `#658682`, `#577A76`, and `#496E6B`; `#577A76` is UI-safe against the canvas (`3.93:1`), while the core `#496E6B` is text-safe (`4.70:1`). Wave strokes are decorative; state is also expressed in text. This motion is limited to Ask LARA.

### Knowledge graph exception

The knowledge workspace lazy-loads `react-force-graph-3d` and Three.js only when opened. It uses a typed adapter over explicitly linked bundled fixture rows, with an accessible list/detail path. The bundled graph is labeled prototype data; it is not a trusted authorization boundary or persistent backend graph. Live graph use requires an authorized room-filtered API response with source provenance before records reach the renderer.

## Direction contract

- Smoky field notes: clear lists and columns, warm capture paper, calm local context.
- Preserve the existing route set and browser-local persistence. Every prototype action remains labeled as simulated.
- No gradient, glass treatment, fake metrics, decorative graph, or externally loaded assets.
