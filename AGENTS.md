# Orac Agent Instructions

Before making changes, read this file first.

Do not read every guardrail document automatically. Select the relevant guardrails based on the files being changed and the nature of the task.

If the task crosses multiple areas, read all relevant guardrails.

If unsure, read the stricter or more relevant document rather than guessing.

## Always read

- docs/agent-guardrails/00-project-principles.md
- docs/agent-guardrails/10-architecture-boundaries.md

## Database, DDL, SQL, install scripts, grants, schemas

Read:

- docs/agent-guardrails/20-database-standards.md

Also read:

- docs/agent-guardrails/25-plsql-standards.md

when changing:

- packages
- package bodies
- procedures
- functions
- triggers
- PL/SQL install blocks
- dynamic SQL
- TAPI/XAPI logic

## Python

Read:

- docs/agent-guardrails/30-python-standards.md

when changing:

- Python application code
- Python scripts
- command line tools
- tests
- packaging code
- plugin runtime code implemented in Python

## Plugins

Read:

- docs/agent-guardrails/50-plugin-standards.md

when changing:

- plugin manifests
- plugin discovery
- plugin registration
- plugin routing
- plugin runtime
- plugin capability definitions
- plugin schemas
- plugin implementations
- gateway plugins

Also read:

- docs/agent-guardrails/60-security-and-risk.md

when plugin changes involve:

- permissions
- external services
- credentials
- network access
- filesystem access
- database writes
- device control
- user data
- LLM access
- context injection

## Security and risk

Read:

- docs/agent-guardrails/60-security-and-risk.md

when changing anything involving:

- credentials
- secrets
- authentication
- authorisation
- grants
- dynamic SQL
- shell execution
- filesystem access
- external APIs
- plugin permissions
- home automation control
- user data
- audit logging
- confirmation flows
- risky actions

## Context management

Read:

- docs/agent-guardrails/70-context-management.md

when changing anything involving:

- conversation history
- messages
- message roles
- message types
- context assembly
- summaries
- tool calls
- tool results
- plugin provenance
- LLM prompts
- context-window management
- stale context handling

## Table abbreviations

Read:

- docs/agent-guardrails/table-abbreviations.csv

before creating or renaming:

- tables
- constraints
- indexes
- triggers
- TAPI packages
- object names derived from table abbreviations

Do not invent table abbreviations.

## Conflict handling

If two guardrails appear to conflict:

1. Prefer the more specific guardrail.
2. Prefer the guardrail closest to the changed code.
3. Preserve existing working project conventions unless explicitly asked to refactor.
4. Ask for clarification before making a schema, security, plugin, or context-management decision that changes architecture.

## Non-negotiable rules

- Do not bypass Orac schema boundaries.
- Do not bypass plugin registration or policy.
- Do not bypass context management.
- Do not expose secrets.
- Do not execute LLM-generated SQL or shell commands.
- Do not grant broad privileges to fix errors.
- Do not rename existing objects unless explicitly instructed.
