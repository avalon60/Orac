---
name: architecture-drift-audit
description: Audit a repository for architectural drift, boundary blurring, stale or contradictory guidance, duplicated pathways, unsafe bypasses, and missing executable checks without editing files. Use when asked to audit architecture drift, inspect repo boundaries, find guardrail drift, review whether code/docs/tests/config still match intended architecture, or produce a remediation plan before implementation.
---

# Architecture Drift Audit

Perform an audit-only pass. Do not edit files, stage changes, run formatters that write files, or normalize drift into a new standard.

## Workflow

1. Read the nearest repo guidance first:
   - `AGENTS.md` or equivalent agent/developer instructions.
   - Architecture, design, guardrail, security, plugin, database, frontend/backend, generated-code, and deployment docs that are relevant to the repository.
   - Existing executable guardrail checks and their tests when present.
2. Establish the intended architecture before judging drift:
   - Main subsystems and ownership boundaries.
   - Allowed dependency directions.
   - Persistence and data-access boundaries.
   - API, service, plugin, extension, frontend/backend, generated-code, security, auth, and audit boundaries where present.
3. Inspect representative evidence:
   - README and developer documentation.
   - Agent guidance such as `AGENTS.md`.
   - Architecture/design docs.
   - Package/module layout and dependency manifests.
   - Test layout and build/lint/test configuration.
   - Representative source files from each major subsystem.
   - Scripts, migrations, deployment, and configuration files where relevant.
4. Look for architectural drift and boundary blurring:
   - Direct imports across intended layers.
   - Business logic in controllers, routes, UI, scripts, migrations, or tests.
   - Data access bypassing intended API/repository/service layers.
   - Duplicated abstractions that solve the same problem.
   - Generic standards that still contain product-specific or team-specific assumptions.
   - Feature-specific rules leaking into general standards.
   - Source code becoming the only source of architectural truth.
   - Tests that encode the wrong architecture.
   - Configuration or scripts that bypass runtime policy.
   - Broad permissions, grants, or access patterns.
   - Circular dependencies.
   - Naming that hides architectural intent.
   - Dead, stale, or contradictory documentation.
   - Missing executable checks for important architectural rules.

## Audit Rules

- Do not assume existing code is correct just because it exists.
- Do not assume documentation is correct just because it is written confidently.
- Distinguish deliberate exceptions from accidental erosion.
- Prefer small enforceable guardrails over broad aspirational guidance.
- Do not propose large rewrites unless drift is severe and evidence supports it.
- Where uncertain, say what evidence is missing.
- If a command would be expensive, destructive, or environment-sensitive, explain why it was not run.

## Severity

- `Critical`: Boundary violation that can cause security, data integrity, or major maintainability risk.
- `High`: Architectural bypass or duplicated pathway likely to worsen.
- `Medium`: Unclear ownership, weak convention, or inconsistent pattern.
- `Low`: Documentation hygiene, naming, or small consistency issue.

## Finding Format

For each finding, report:

- Title.
- Severity.
- Evidence with file paths.
- Why it represents drift or boundary blurring.
- Likely impact.
- Recommended fix.
- Fix type: documentation, test coverage, static check, refactor, or deletion.
- Whether it can be handled safely as a small change.

## Final Output

Return:

1. Intended architecture summary.
2. Drift findings by severity.
3. Boundary map.
4. Recommended guardrails.
5. Recommended executable checks.
6. Suggested small first remediation task.
7. Things not checked or requiring human confirmation.
