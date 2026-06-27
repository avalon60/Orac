# AI-Generated Code Reviewability

## Purpose

This document defines language-neutral reviewability rules for code created or
significantly changed by an AI agent.

Use it together with the applicable language, framework, database, security,
and git workflow guardrails. It applies to generated or agent-authored code in
any language.

## When to Apply

Apply these rules when creating new code or making significant changes to
existing code, including:

- application code
- scripts and command line tools
- database code and install logic
- standalone utility scripts, even when placed at the repository root
- SQL*Plus, SQLcl, shell, or PL/SQL helper scripts that execute database,
  APEX, privilege, ACL, grant, install, restore, or provisioning actions
- frontend components
- tests and test harnesses
- generated or scaffolded source files

A new executable or operational helper is always in scope for review notes,
even if it is short, manually invoked, environment-specific, or not part of a
formal deployment path.

Small mechanical edits, formatting-only changes, and documentation-only changes
do not require a full reviewability note unless they materially affect code
behaviour, interfaces, operations, or review risk.

## Required Review Notes

For new code or significant code changes, provide concise review notes in the
final response, pull request description, change summary, or equivalent review
handoff.

The notes must describe the final design and observable implementation, not the
agent's internal reasoning process.

Include:

1. Short purpose statement

   State what the changed code is for in one or two sentences.

2. Requirement coverage notes

   Map explicit requirements to the delivered behaviour. Identify any
   requirement that is partial, deferred, or intentionally out of scope.

3. Assumptions and constraints

   State relevant project conventions, compatibility limits, operational
   constraints, data assumptions, security assumptions, or invariants.

4. Design trade-offs

   Record the important trade-offs visible in the final design, such as
   compatibility over refactoring, simplicity over extensibility, synchronous
   behaviour over background work, or reuse of an existing boundary over a new
   abstraction.

5. Reviewer checkpoints

   Point reviewers to the files, flows, tests, edge cases, permissions,
   migrations, fallback paths, or failure modes most worth inspecting.

Keep each item short and objective. If an item has no meaningful content, write
`None identified` rather than inventing justification.

## What Not To Include In Review Notes

Do not include:

- hidden chain-of-thought or step-by-step internal deliberation
- prompt transcripts or agent self-narration
- a chronological diary of how the code was produced
- unverifiable claims about quality or safety
- speculation that is not grounded in the final implementation

It is acceptable to mention generator inputs, regeneration commands, or source
artifacts when those are part of the maintained design contract for a generated
file.

## Code Comment Rules

Code comments should explain information that future maintainers cannot easily
infer from names, structure, types, tests, or nearby code.

Use code comments to explain:

- intent behind non-obvious logic
- invariants and lifecycle assumptions
- compatibility, security, data, or operational constraints
- important side effects and external dependencies
- non-obvious edge cases or failure behaviour
- why a locally unusual pattern is required

Avoid comments that:

- restate obvious syntax or names
- describe how the code was produced
- mention that an AI agent generated or changed the code
- narrate development history that belongs in review notes or commit history
- preserve dead or commented-out code
- justify unsafe shortcuts
- duplicate the required review notes inside source files

Prefer clear names, small functions, explicit contracts, and focused tests over
heavy commentary. Add comments only where they reduce review or maintenance
risk.

## Agent Enforcement Rules

When generating or significantly changing code, agents must:

- provide the required review notes before handing off the change for review
- keep review notes concise, objective, and final-design focused
- apply these rules across programming, scripting, database, frontend, and test
  languages
- keep source comments focused on intent, invariants, constraints, and
  non-obvious behaviour
- avoid using source comments to describe the AI generation process
