# Frontend Next.js Standards

## Purpose

This document defines frontend guardrails for Next.js application work.

These rules apply only when the task involves a frontend Next.js application,
including Next.js pages, layouts, route segments, React components, client
components, server components, frontend data-fetching flows, metadata, images,
fonts, bundle behaviour, hydration, or frontend performance.

Do not load these guardrails for database work, backend-only services, Python
tooling, generic documentation updates, non-Next.js React applications, or
application areas where Next.js is not present.

## Confirm Next.js Scope First

Before applying these guardrails, confirm the current application is a Next.js
frontend application by checking local evidence such as:

- `package.json` dependency on `next`
- `next.config.js`, `next.config.mjs`, or `next.config.ts`
- App Router files such as `app/layout.tsx`, `app/page.tsx`, or
  `app/**/route.ts`
- Pages Router files such as `pages/_app.tsx`, `pages/index.tsx`, or
  `pages/api/**`
- existing project context that explicitly identifies the app as Next.js

If the evidence is unclear, inspect neighbouring files or ask before applying
Next.js-specific guidance.

## Reference Loading Rules

This guardrail is the default frontend Next.js standard. Load additional
reference files only when they are relevant to the specific task.

- Use `docs/agent-guardrails/frontend-nextjs/nextjs/index.md` as reference
  material when the task needs deeper Next.js details about file conventions,
  routing, React Server Component boundaries, async framework APIs, metadata,
  image/font usage, route handlers, bundling, hydration, Suspense, or
  App/Pages Router conventions.
- Use `docs/agent-guardrails/frontend-nextjs/react-performance/index.md` as
  reference material when the task needs deeper React or Next.js frontend
  performance guidance about waterfalls, bundle size, server/client rendering,
  data fetching, re-rendering, hydration, JavaScript execution cost, or
  rendering performance.

These reference docs are not skills. Do not load them wholesale by default;
open the relevant index or rule files only when the current task needs that
detail.

## Frontend Architecture Rules

- Follow the framework, package manager, routing model, and component layout
  already present in the target app.
- Preserve App Router or Pages Router conventions already used by the app.
- Keep server-only code out of client bundles.
- Keep browser-only code out of server modules.
- Do not add broad `'use client'` boundaries to make errors disappear.
- Keep props crossing React Server Component boundaries serializable unless an
  approved framework exception applies.
- Do not introduce async client components.
- Prefer server components for data access and rendering that does not require
  browser state or browser APIs.
- Use client components for interactivity, browser APIs, stateful UI, and event
  handlers.
- Preserve existing authentication, authorisation, data-access, and context
  mediation paths.

## Next.js Data And Routing Rules

- Use the app's existing data-fetching pattern unless the task explicitly asks
  for a migration.
- Avoid data waterfalls; start independent work early and await it together
  where the local pattern allows.
- Treat Server Actions as authenticated mutation endpoints, not trusted client
  callbacks.
- Use Route Handlers for HTTP API surfaces and integration endpoints.
- Do not create a `GET` route handler where it conflicts with a page route in
  the same segment.
- Handle framework async APIs according to the app's installed Next.js version.
- Keep redirects, not-found flows, error boundaries, and global error handling
  aligned with existing route conventions.

## Accessibility Rules

- Prefer semantic HTML before adding custom roles or scripted behaviour.
- Preserve keyboard navigation for interactive controls and workflows.
- Maintain visible focus states.
- Use ARIA sparingly and only where semantic HTML is insufficient.
- Do not introduce inaccessible icon-only controls; provide an accessible name.
- Respect reduced-motion preferences for animation and transitions.
- Consider colour contrast when changing visual styling.

## Styling And Design-System Rules

- Inspect the app's existing styling approach before adding new patterns.
- Reuse existing components, tokens, CSS modules, Tailwind conventions, or
  styling utilities where present.
- Do not introduce a second design system casually.
- Keep app-specific styling local unless there is clear shared reuse.
- Avoid broad global CSS changes unless the task explicitly requires them.

## Forms And Client State Rules

- Keep form validation clear and close to the form boundary.
- Provide pending, success, and error states for user actions.
- Avoid unnecessary global state.
- Prefer URL state for shareable filters, search, and sort state where
  appropriate.
- Be careful with optimistic updates and ensure failure recovery is defined.

## User-Facing UX State Rules

- Handle loading, empty, error, unauthorised, not-found, and responsive states.
- Do not leave blank screens or silent failures.
- Preserve useful feedback during long-running actions.
- Keep mobile and narrow viewport behaviour in scope when changing layouts.

## Performance And Bundle Rules

- Avoid importing large packages into client components when a smaller,
  server-only, or dynamically loaded path is available.
- Prefer direct imports over barrel imports when bundle size or tree shaking may
  be affected.
- Use `next/image` and `next/font` where the app already uses standard Next.js
  optimisation paths.
- Keep third-party scripts and analytics out of the critical path unless the
  product requirement makes them critical.
- Use Suspense boundaries deliberately for streamed or deferred content.
- Avoid memoization that adds complexity without reducing meaningful work.
- Fix hydration mismatches by removing the mismatch or isolating expected
  client-only values; do not suppress warnings without justification.

## Frontend Security And Privacy Rules

- Never expose secrets through client code or public environment variables.
- Treat `NEXT_PUBLIC_*` values as visible to users.
- Avoid `dangerouslySetInnerHTML` unless explicitly justified and sanitised.
- Be cautious with third-party scripts, telemetry, and external embeds.
- Preserve existing authentication and authorisation boundaries.

## Dependency Policy Rules

- Prefer existing project dependencies and utilities.
- Do not add large frontend packages for small UI changes.
- Justify new dependencies by need, bundle impact, maintenance cost, and
  existing alternatives.
- Avoid introducing overlapping libraries for the same purpose.

## Monorepo Shared Component Rules

- Keep shared UI package versions centralized across apps.
- Keep components used by only one app inside that app and import them directly
  within that app.
- Move components used by more than one app or region into the shared
  components area and update all consumers to import from there.
- Do not import components directly from one app into another app.
- Keep shared components app-agnostic; pass region-specific text, links,
  permissions, data, and callbacks as props.

## Testing Expectations

- Match validation to the risk of the change.
- Use type checks, linting, unit tests, component tests, or browser tests as
  appropriate to the app.
- Add interaction tests for meaningful user flows, form behaviour, state
  transitions, or regressions.
- Do not rely only on visual inspection for non-trivial behaviour changes.

## Validation

Use the narrowest validation that proves the frontend change is sound:

- file-level type checks or lint checks when available
- app-level lint or typecheck
- targeted component, route, or browser tests
- a production build for routing, bundling, metadata, or server/client boundary
  changes

Use the package manager and scripts already present in the app. If no suitable
validation exists, state the gap and the manual checks performed.
