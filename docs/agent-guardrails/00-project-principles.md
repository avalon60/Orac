# Orac Project Principles

This document defines the core design principles of Orac.

These principles are non-negotiable.
All code changes must comply with them.

---

## 1. Orac is Architecture-First

- Orac is a system, not a collection of scripts.
- All changes must preserve the existing architecture unless explicitly instructed otherwise.
- Do not introduce shortcuts that bypass defined layers or boundaries.

---

## 2. Separation of Concerns is Mandatory

- ORAC_CORE owns data structures only.
- ORAC_API provides controlled access to ORAC_CORE.
- ORAC_CODE implements business logic.

- Do not:
  - access ORAC_CORE tables directly from ORAC_CODE
  - bypass ORAC_API with ad-hoc SQL
  - duplicate logic across layers

---

## 3. Principle of Least Privilege (POLP)

- All access must be explicitly granted and minimal.
- Do not introduce broad or convenience privileges.
- Do not grant direct table access to consumer schemas.

---

## 4. Plugins Extend Orac — They Do Not Control It

- Plugins are consumers of Orac capabilities.
- Plugins must not:
  - modify core schemas directly
  - bypass Orac APIs
  - redefine orchestration or routing logic

- All plugin interactions must go through defined interfaces.

---

## 5. The Content Engine is the Control Point

- All conversational input and output must pass through the content engine.
- Do not bypass or duplicate content handling logic.
- Do not embed ad-hoc prompt logic outside the content engine.

---

## 6. LLMs Are Constrained Components

- LLMs must not:
  - generate or execute arbitrary SQL
  - generate or execute shell commands
  - perform privileged operations

- LLMs provide interpretation and reasoning, not control.

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
