# Frontend Vite React Standards

## Purpose

These guardrails apply to Orac browser applications that use Vite, React,
TypeScript, and browser-rendered UI. They are written for the current
`web/orac-display` app.

Do not apply Next.js, React Server Component, App Router, route handler,
`next/image`, `next/font`, or server action guidance to Orac web work unless a
real Next.js app is introduced and documented in `web/AGENT_CONTEXT.md`.

## Scope Detection

Before applying these rules, confirm the target is the Orac Vite display app:

- path is under `web/orac-display`
- `package.json` uses `vite`, `react`, `typescript`, and `@vitejs/plugin-react`
- the app entry is `src/App.tsx`
- the local bridge is `bridge.js`
- runtime transport defaults to `ws://127.0.0.1:8767`

For any file under `web`, first read `web/AGENTS.md` and
`web/AGENT_CONTEXT.md`. If the target is not `web/orac-display`, inspect the
local app before applying these rules.

## Application Boundary

`web/orac-display` is a thin browser display/control surface for Orac runtime
state. Preserve that boundary unless the user explicitly asks for a broader
control surface.

- Keep browser-only code inside the web app.
- Keep runtime bridge/server code separate from React components unless an
  existing file intentionally owns that boundary.
- Do not move APEX exports, database assets, Python runtime code, or plugin
  implementation code into `web`.
- Treat controls that affect Orac runtime state as security-sensitive.
- Do not expose secrets, bearer tokens, credential URLs, local file paths, or
  private runtime details in browser state, logs, DOM, or screenshots.
- Keep operator-facing status information bounded to current display state.
  Historical conversation, plugin internals, and raw runtime diagnostics should
  not become permanent browser-visible state unless the task explicitly asks for
  that surface and the security guardrails are reviewed.

## Vite, React, And TypeScript

- Follow the existing Vite project layout and npm scripts.
- Use TypeScript types for inbound WebSocket payloads and component props.
- Keep state local unless it is genuinely shared across independent components.
- Use refs for mutable transport handles, animation handles, and transient
  values that should not re-render the UI.
- Use functional `setState` when deriving new state from previous state.
- Derive simple render values during render instead of mirroring them into
  effects.
- Avoid defining React components inside other components.
- Use memoization only when it avoids meaningful repeated work or stabilizes a
  dependency that matters.
- Clean up timers, animation frames, event listeners, WebSocket handlers, and
  Three.js resources in effects.

## Transport And Local Bridge

The display consumes a reconnecting WebSocket stream from the local Orac
display bridge.

- Preserve reconnect, disconnected, offline, and quiet logging behaviour.
- Maintain compatibility aliases already documented by `web/orac-display`,
  including legacy transcript and stream event names.
- Validate or defensively narrow unknown payloads before reading fields.
- Keep payload parsing tolerant of missing optional fields.
- Do not make browser UI state the source of truth for Orac runtime state.
- Keep connection diagnostics useful but quiet by default; use existing
  diagnostic flags and helpers where present.
- Do not remove compatibility event aliases unless the corresponding Python or
  bridge producer has already stopped emitting them.
- Avoid logging every reconnect or transient stream payload by default. The
  display is often used in kiosk mode, and noisy logs hide real WebGL,
  transport, or payload-shape failures.
- Treat data received over the WebSocket as untrusted shape-wise, even though it
  is local. Handle unknown events by ignoring them or routing them through
  existing diagnostics rather than throwing in the render path.

## Three.js And Canvas

The main visual surface uses React Three Fiber, Three.js, postprocessing, and
WebGL diagnostics.

- Verify canvas work in a browser, not only by compiling TypeScript.
- Preserve WebGL context loss/restoration handling and canvas error boundaries.
- Keep a visible fallback for canvas failure, connection failure, and loading.
- Respect `prefers-reduced-motion` and existing reduced-motion hooks.
- Dispose of geometries, materials, textures, render targets, and listeners
  when adding long-lived Three.js resources.
- Avoid unbounded per-frame allocations in `useFrame`.
- Keep canvas dimensions and overlays responsive for desktop, kiosk, and narrow
  viewport use.
- Check that 3D content is nonblank, centered, and not hidden behind overlays.
- Keep generated canvas textures, materials, and animation constants stable
  across renders unless they intentionally depend on state.
- Do not let fallback UI obscure the ability to see whether the canvas is
  blank, crashed, reconnecting, or deliberately idle.
- Preserve existing diagnostic events for `webglcontextlost`,
  `webglcontextrestored`, and display recovery requests.

## UI And Styling

- Reuse the app's existing styling approach, Tailwind-style utility classes,
  component structure, colours, and motion language.
- Preserve the appliance/kiosk feel: clear status, readable transcript panels,
  and resilient disconnected states.
- Keep text inside its containers on narrow and desktop viewports.
- Avoid overlapping status pills, transcript panels, state buttons, and canvas
  overlays.
- Preserve keyboard accessibility and accessible names for interactive
  controls.
- Respect reduced motion for animations and transitions.
- Do not add a second component library or styling system for small UI changes.
- Prefer existing icons and dependencies before adding new packages.
- Keep status labels, identity pills, transcript panels, and the optional state
  button rail readable over the animated canvas.
- Long transcript text must wrap or scroll inside its panel without pushing the
  canvas or fixed controls out of frame.
- The disconnected state should be visually distinct from idle/listening/
  thinking/speaking states.
- Do not introduce marketing-page patterns, hero layouts, or decorative content
  into the display app. The first screen is the appliance UI.

## Assets And Dependencies

- Keep visual assets local to the web app unless they are shared by an existing
  documented asset pipeline.
- Prefer CSS, existing icons, or existing Three.js primitives before adding
  bitmap assets.
- Do not add heavyweight rendering, charting, animation, or state-management
  packages without checking whether React, Three.js, Framer Motion, or existing
  utilities already cover the need.
- Keep package changes in `web/orac-display/package.json` and its lockfile only
  when a dependency change is actually required.

## Performance Essentials

Use compact React/browser performance rules that matter for this app:

- Avoid expensive work during every render; precompute or memoize only when it
  removes real repeated cost.
- Avoid unnecessary global event listeners; deduplicate and clean them up.
- Use passive listeners for scroll/touch listeners where appropriate.
- Use `Promise.all` for independent async work.
- Defer non-critical background work with browser idle callbacks only where a
  fallback exists.
- Prefer `Set` or `Map` for repeated lookups over repeated array scans.
- Avoid mutating arrays or objects held in React state.
- Keep heavy optional UI or diagnostics off the critical path.

## Validation

Run validation from `web/orac-display` unless the task is documentation-only:

```bash
npm run lint
npm run build
```

For visual, canvas, transport, or layout changes, also run the app and verify in
a browser:

- normal desktop viewport
- narrow/mobile-like viewport
- disconnected or reconnecting WebSocket state
- transcript panels when `VITE_ORAC_SHOW_TRANSCRIPT_PANELS=true`
- WebGL/canvas renders nonblank and remains framed correctly
- state-button rail when launched with browser buttons enabled, if the change
  touches controls or layout
- reduced-motion mode when the change touches animation or transitions

If a local browser or WebSocket bridge is unavailable, say exactly what was not
verified.
