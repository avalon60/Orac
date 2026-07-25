# Web Application Agent Context

This file contains Orac-specific mappings for browser-based web applications
under `web`.

## Application Surface Split

Orac has two distinct application surfaces:

- APEX applications are database-delivered application assets under
  `resources/db/apex`.
- Web applications are browser/runtime application assets under `web`.

Do not treat these surfaces as interchangeable.

APEX workspace exports and APEX application exports are governed by:

- `resources/db/apex/AGENTS.md`
- `resources/db/apex/AGENT_CONTEXT.md`

## Current Web Applications

| Namespace | Application name | Root path | Guidance index |
|---|---|---|---|
| `orac-display` | Orac Display Web | `web/orac-display/` | `none` |

## `web/orac-display`

`web/orac-display` is a browser display/control surface for Orac runtime state.
It is designed for standalone browser windows, kiosk displays, and local
development display tabs.

| Surface | Kind | Framework/runtime | Layout convention | Responsibility |
|---|---|---|---|---|
| `web` | `web-ui` | Vite, React, TypeScript, Three.js | Repository-specific single Vite application | Thin browser display and bounded local control surface |

Placement mapping:

- `web/orac-display/package.json` defines the npm scripts and dependencies.
- `web/orac-display/src/App.tsx` is the app entry component.
- `web/orac-display/src/components/` contains display components.
- `web/orac-display/public/` contains static assets.
- `web/orac-display/vite.config.ts` owns Vite build configuration.
- `web/orac-display/bridge.js` is the local bridge surface used by the display
  workflow.
- `web/orac-display/README.md` documents launch and transport behaviour.

Runtime notes:

- The app is Vite/React, not Next.js.
- Active frontend guardrails live in
  `docs/agent-guardrails/35-frontend-vite-react-standards.md`.
- The default browser endpoint is `http://localhost:5173`.
- The display WebSocket defaults to `ws://127.0.0.1:8767`.
- `bin/orac-web-display.sh` is the preferred local launcher for the display
  workflow.
- Shared production packages under `web/common/`: `none`.
- Keep application-owned dependencies in `web/orac-display/package.json`.
- The app should remain a thin display/control surface unless the task
  explicitly changes that boundary.

## Project-Specific Invariants

- Do not move APEX exports into `web`.
- Do not apply APEX parsing-schema assumptions to web app source code.
- Do not apply web packaging assumptions to APEX export files.
- Preserve browser/runtime transport boundaries when changing display features.
- Treat any new browser control that can affect Orac runtime state as
  security-sensitive and review it against the root security guardrails.
- Colocated tests under `web/orac-display/` are owned by this surface.
- Integration or controller tests outside `web/` remain owned by their
  existing root test suites; no non-production web suite is declared.

## Validation

From `web/orac-display`, run `npm run lint` and `npm run build`. Run the
applicable package test command when `package.json` declares one. For visual,
transport, canvas, or layout work, also verify representative browser states
and viewports using `bin/orac-web-display.sh`.
