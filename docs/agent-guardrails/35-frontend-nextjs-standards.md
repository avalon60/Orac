# Frontend Next.js Standards

## Purpose

This document defines frontend guardrails for Next.js application work.

These rules apply only when the task involves a frontend Next.js application,
including Next.js pages, layouts, route segments, React components, client
components, server components, frontend data-fetching flows, metadata, images,
fonts, bundle behaviour, hydration, or frontend performance.

Do not load these guardrails or operational frontend skills for database work,
backend-only services, Python tooling, generic documentation updates,
non-Next.js React applications, or application areas where Next.js is not
present.

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

## Operational Skill Loading Rules

Load project-local frontend skills only for narrow frontend Next.js operational
workflows.

- Use `.agents/skills/nitro-components/SKILL.md` when writing, reviewing, or
  refactoring UI in apps that import `@idp/nitro-redwood` and
  `@idp/nitro-providers` directly rather than through a wrapper package.

Do not load these skills for:

- Oracle Database, SQL, PL/SQL, or Liquibase tasks
- backend-only services or scripts
- non-Next.js React applications
- documentation-only work unless the documentation is specifically about a
  frontend Next.js application
- generated output review where no frontend Next.js source or behaviour is in
  scope
- general Next.js or React best-practice lookup that is better answered by the
  guardrail references above

When a task touches both frontend Next.js and other layers, load the frontend
skills only for the frontend portion and continue to follow the relevant
database, security, Python, or git guardrails for the other portions.

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

## Monorepo Shared Component Rules

- Keep shared UI package versions centralized across apps.
- Keep `@idp/nitro-redwood` versioned through the monorepo's established global
  dependency mechanism, not independently in each app.
- Keep components used by only one app inside that app and import them directly
  within that app.
- Move components used by more than one app or region into the shared
  components area and update all consumers to import from there.
- Do not import components directly from one app into another app.
- Keep shared components app-agnostic; pass region-specific text, links,
  permissions, data, and callbacks as props.

## Nitro Direct Component Rules

When a Next.js app imports `@idp/nitro-redwood` or `@idp/nitro-providers`
directly, prefer installed Nitro primitives before building custom React UI.

- Inspect the app's package manifest and existing imports before changing UI.
- Discover available Nitro components from `node_modules`, especially
  `node_modules/@idp/nitro-redwood/dist/types` and
  `node_modules/@idp/nitro-redwood/dist/esm`.
- Import UI directly from `@idp/nitro-redwood` and provider/runtime helpers
  directly from `@idp/nitro-providers` only when needed.
- Keep app-owned styling focused on layout, spacing, placement, sizing,
  responsive behaviour, map/background containers, and overlays.
- Do not recolor Nitro components, override Nitro internal classes, restyle
  Nitro chrome, or replace Nitro visual language with app-owned CSS.
- Do not recreate Nitro buttons, chips, badges, navigation, cards, search
  inputs, or page primitives with custom markup when Nitro provides a matching
  component.
- If a requested visual change conflicts with Nitro's native design, compose
  Nitro components differently before proposing stronger visual overrides.

## Validation

Use the narrowest validation that proves the frontend change is sound:

- file-level type checks or lint checks when available
- app-level lint or typecheck
- targeted component, route, or browser tests
- a production build for routing, bundling, metadata, or server/client boundary
  changes

Use the package manager and scripts already present in the app. If no suitable
validation exists, state the gap and the manual checks performed.
