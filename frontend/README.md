# LARA IV frontend

LARA IV is a browser-local productivity workspace prototype. Ask LARA is the starting screen; Today, Inbox, Kanban, Calendar, Reminders, Projects & Memory, and Operations & Governance remain available in the sidebar.

## Run locally

```bash
npm install
npm run dev
```

## Checks

```bash
npm run build
npm run lint
```

## Prototype boundary

The UI uses a typed mock adapter and browser storage. Conversation responses are static demo copy. There is no connected model provider, backend API, operating-system integration, or external tool execution. Task, reminder, approval, and settings actions modify browser-local demo data only.

Conversation history is grouped by stable conversation IDs. Existing flat browser message arrays migrate into one legacy conversation in memory; the two known seeded demo message IDs are the only messages omitted. Starting a conversation does not clear older threads.

The knowledge graph uses the lazy-loaded [`react-force-graph-3d`](https://github.com/vasturiano/react-force-graph) renderer over explicitly linked bundled fixture records. Node and edge labels, relationship explanations, and provenance strings are prototype data. Local paths and hash metadata are redacted. No verified backend graph read endpoint exists yet; live use depends on an authorized, room-filtered graph endpoint that returns nodes, typed edges, source citations, and provenance after policy checks.

The app intro uses the original repository `logo.png` without modifying it. Ask LARA's layered SVG wave animates locally and does not indicate inference or tool activity.

The Python `ubuntu_agent` package and backend contracts remain separate from this frontend prototype.
