# Web Application Agent Instructions

This file contains reusable guidance for Orac browser-based web applications
under `web`.

Keep project-specific application names, runtime details, transport contracts,
ports, and deployment notes in the adjacent `AGENT_CONTEXT.md` file.

## Required Context

Before changing, generating, moving, or reviewing web application assets under
this tree, read the adjacent `AGENT_CONTEXT.md`.

If the context file is missing or incomplete for the application being changed,
inspect the local application files and flag the documentation gap in your
response.

## Scope

The `web` tree is for browser-based applications and related web runtime assets.

APEX applications are not part of this tree. APEX workspace exports and APEX
application exports are database assets under `resources/db/schema` and are
governed by `resources/db/schema/AGENTS.md`.

## Working Rules

- Follow the framework, package manager, routing model, and component layout
  already present in the application being changed.
- Keep browser-only code out of Python runtime modules.
- Keep server/runtime bridge code separate from browser component code unless
  the existing application intentionally colocates them.
- Treat WebSocket transports, local bridge services, filesystem access,
  generated content, credentials, and user data as security-sensitive.
- Preserve the thin-display boundary for display-only apps unless the user
  explicitly asks for a broader control surface.
- Do not move code between web applications or introduce a new web application
  directory without documenting it in `AGENT_CONTEXT.md`.

## Frontend Guidance

Use the root frontend instructions for user-facing UI quality. Only use
framework-specific guardrails when they match the application actually being
changed.

For the current Vite/React display app, read:

- docs/agent-guardrails/35-frontend-vite-react-standards.md

Do not apply Next.js-specific routing, server component, or app-router
assumptions. Archived Next.js reference material under `docs/reference-archive/`
is optional reference only and is inactive unless a real Next.js app is added to
this repository.
