---
name: architecture-drift-remediation
description: Implement lightweight architecture drift controls from a reviewed audit, using small documentation hygiene fixes, guardrail updates, executable checks, and focused tests. Use after an architecture drift audit when asked to remediate findings, add guardrails, add drift checks, tighten AGENTS.md routing, or make architecture rules executable without large refactors or runtime behavior changes.
---

# Architecture Drift Remediation

Turn reviewed audit findings into small, maintainable controls. Do not use this skill for the initial audit-only pass; use `architecture-drift-audit` first when findings have not been established.

## Constraints

- Keep changes minimal and reviewable.
- Do not rewrite architecture.
- Do not introduce heavy dependencies unless they are already standard in the repo.
- Prefer standard tooling already present in the repo.
- Prefer executable checks over more prose where practical.
- Do not change runtime behavior unless explicitly requested.
- Do not normalize accidental drift as a new standard.
- Do not implement large refactors unless the user explicitly asks for them after reviewing the audit.
- Respect all repo-specific guidance in `AGENTS.md` and guardrail docs.

## Workflow

1. Read the previous audit and identify the reviewed findings to address.
2. Re-read the repo guidance that applies to the files being changed:
   - Root `AGENTS.md` or equivalent.
   - Architecture and guardrail docs.
   - Subdirectory-specific guidance for touched files.
3. Select small controls that reduce future drift:
   - Documentation hygiene.
   - Routing updates in `AGENTS.md` or equivalent.
   - Lightweight static checks.
   - Focused tests for those checks.
4. Avoid fragile checks:
   - Do not encode accidental current repository state.
   - Do not add broad forbidden-pattern checks unless the boundary is clear.
   - Do not fail on known drift unless this pass also fixes or explicitly scopes it.
5. Implement the selected changes with narrow diffs.
6. Run focused validation:
   - Run the checker directly.
   - Run tests for the checker.
   - Run relevant lint/type/test commands that are not excessive.
7. Report any current repo issues detected by the checker.

## Documentation Controls

Prefer concise, enforceable updates:

- Remove stale, duplicated, or product-specific wording from generic standards.
- Clarify ownership boundaries where they are ambiguous.
- Add missing references from `AGENTS.md` or equivalent routing guidance.
- Split or rename docs only when that is the smallest clear fix.
- Add an ADR or short design note only when an important boundary is not documented anywhere.

## Executable Checks

Prefer lightweight checks that fit existing tooling:

- Validate referenced architecture and guardrail docs exist.
- Reject stray temporary, untitled, or placeholder docs when the repo has a clear docs convention.
- Check naming conventions for architectural guardrail files.
- Check forbidden imports or direct access only where the boundary is explicit.
- Check plugin, database, generated-code, or frontend/backend boundaries only when repo guidance defines the rule clearly.

## Tests

- Add tests for the checker itself.
- Use temporary fixtures where practical.
- Avoid tests that pass only because the current known drift was cleaned up.
- Add architectural invariant tests only where the intended rule is clear.

## Final Output

Return:

- Files changed.
- Checks added.
- Tests added.
- Commands run.
- Results.
- Remaining drift not fixed in this pass.
- Recommended next small task.
