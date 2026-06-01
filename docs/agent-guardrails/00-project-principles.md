# Project Principles

This document defines the core design principles for the project.

These principles are non-negotiable.
All code changes must comply with them.

---

## 1. The Platform Is Architecture-First

- The platform is a system, not a collection of scripts.
- All changes must preserve the existing architecture unless explicitly instructed otherwise.
- Do not introduce shortcuts that bypass defined layers or boundaries.

---

## 2. Separation of Concerns Is Mandatory

- Each domain must preserve its least-privilege schema topology.
- `<DOMAIN>_CORE` owns data structures only.
- `<DOMAIN>_API` provides controlled access to `<DOMAIN>_CORE`.
- `<DOMAIN>_CODE` implements business logic.

- With the exception of approved materialized views, do not:
  - access `<DOMAIN>_CORE` tables directly from `<DOMAIN>_CODE`
  - bypass `<DOMAIN>_API` with ad-hoc SQL
  - duplicate logic across layers

---

## 3. Principle of Least Privilege (POLP)

- All access must be explicitly granted and minimal.
- Do not introduce broad or convenience privileges.
- Do not grant direct table access to consumer schemas.

---

## 4. Plugins Extend the Platform - They Do Not Control It

- Plugins are consumers of platform capabilities.
- Plugins must not:
  - modify core schemas directly
  - bypass approved APIs
  - redefine orchestration or routing logic

- All plugin interactions must go through defined interfaces.

---

## 5. The Context Mediation Layer Is the Control Point

- Where conversational or AI context is part of the architecture, all model-facing input and output must pass through the context mediation layer.
- Do not bypass or duplicate approved context handling logic.
- Do not embed ad-hoc prompt or context assembly logic outside the documented control path.

---

## 6. AI-Assisted Components Are Policy-Constrained

When AI-assisted components are part of the design:

- They must operate within validated, policy-constrained execution paths.
- They must not bypass schema, security, approval, or context boundaries.
- They provide interpretation and generation, not authority.

Detailed execution, SQL, shell, privilege, and approval rules belong in the security, database, and context guardrails.

---

## 7. Explicit Over Implicit

- Prefer explicit definitions over inferred behaviour.
- Do not introduce "magic" behaviour that is not clearly defined.
- Avoid hidden side effects.

---

## 8. Backwards Compatibility Matters

- Do not rename or restructure existing objects without instruction.
- Do not introduce breaking changes silently.
- Existing behaviour takes precedence over theoretical improvements.

---

## 9. Small, Reviewable Changes

- Prefer incremental changes over large rewrites.
- Explain architectural impact before making changes.
- Avoid combining unrelated changes in a single update.

---

## 10. Consistency Over Perfection

- Follow existing patterns, even if they are imperfect.
- Do not refactor purely for stylistic reasons.
- Avoid introducing multiple competing patterns.

---

## Agent Enforcement Rules

Before making changes, agents must:

- Read this document and all relevant guardrails
- Confirm that proposed changes comply with these principles
- Highlight any potential violations before implementation

If a requested change conflicts with these principles:

- Do not proceed silently
- Raise the conflict and request clarification
