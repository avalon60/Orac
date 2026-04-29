---
name: orac-sqlcl
description: Use SQLcl MCP or host SQLcl to inspect and verify the Orac development database safely when checking schemas, objects, constraints, grants, package status, data shape, imports, deployments, or database errors.
---

# Orac SQLcl Database Access

Use the configured SQLcl MCP server for lightweight inspection of the Orac development database.

SQLcl MCP is useful for read-only checks, metadata inspection, object lookups, and quick verification. However, the SQLcl MCP transport can occasionally disconnect or become unreliable. When that happens, use host `SQLcl` with the saved connections as the fallback.

In Codex, host `SQLcl` may still be unable to reach the database from the default sandboxed shell. If a saved connection fails with a network adapter error such as `ORA-17820`, rerun the host `SQLcl` command with escalated permissions so it executes outside the sandbox.

## Preferred Access Order

1. Use SQLcl MCP for lightweight read-only database inspection.
2. If SQLcl MCP disconnects, fails, hangs, or returns inconsistent results, retry once.
3. If it fails again, use host `SQLcl` with one of the saved connections.
4. If host `SQLcl` cannot connect from the sandbox, rerun it with escalated permissions.
5. Use host `SQLcl` for critical post-operation verification.

## Saved SQLcl Connections

Use one of the following saved connections:

```text
orac          - Connect as the ORAC database user (internal Orac connection)
orac-db       - Connect as the SYSTEM user
orac_apx_pub  - Connect as the APEX public/parsing schema (ORAC_APX_PUB)
```

Prefer the least-privileged saved connection that can answer the question.

Use `orac` for internal Orac object checks.

Use `orac_apx_pub` when checking objects visible to the APEX application.

Use `orac-db` only when elevated privileges are genuinely required, such as checking cross-schema grants, invalid objects across schemas, container-level metadata, or installation issues.

## SQLcl MCP Usage

Use SQLcl MCP for:

- checking whether schemas, tables, views, packages, triggers, sequences, and synonyms exist
- inspecting object status
- checking package compilation errors
- checking grants and synonyms
- checking constraints and indexes
- checking table metadata
- checking small samples of data
- diagnosing database errors

Do not rely on SQLcl MCP as the sole execution path for installation, import, deployment, or migration work.

## Host SQLcl Fallback

When SQLcl MCP is unreliable, use host `SQLcl` with the configured saved connections.

In Codex, prefer treating host `SQLcl` as a two-step fallback:

1. Try the saved connection normally.
2. If the connection fails with a network/socket error such as `ORA-17820`, rerun the same command with escalated permissions.

Use this pattern:

```bash
sql /nolog <<'SQL'
conn -name <saved_connection_name>
set pagesize 200
set linesize 200
set feedback on
set heading on
set serveroutput on

-- SQL goes here

exit
SQL
```

Replace `<saved_connection_name>` with one of:

- `orac`
- `orac-db`
- `orac_apx_pub`

Prefer host `SQLcl` fallback for:

- confirming an APEX import completed correctly
- verifying installation or deployment results
- checking invalid objects after install scripts
- checking package compilation errors after deployment
- confirming critical DDL or DML effects
- diagnosing failures where SQLcl MCP transport disconnected

When using the fallback:

- prefer the least-privileged saved connection that can answer the question
- use `orac` for internal Orac object checks
- use `orac_apx_pub` for objects visible to the APEX application
- use `orac-db` only when elevated access is genuinely required
- if a saved connection fails with `ORA-17820` or a similar network adapter error, rerun the command with escalated permissions
- state in the response that SQLcl MCP failed and host `SQLcl` was used instead

## Safety Rules

- Do not run destructive DDL or DML unless explicitly requested.
- Do not drop, truncate, rename, or recreate objects unless explicitly requested.
- Do not silently change schema ownership boundaries.
- Prefer read-only queries when inspecting the database.
- Prefer least-privilege connections.
- Do not expose passwords or secrets in responses.
- When using elevated access, explain why it was necessary.

## Useful Checks

Check invalid objects:

```sql
select owner,
       object_type,
       object_name,
       status
from all_objects
where status <> 'VALID'
order by owner,
         object_type,
         object_name;
```

Check package errors:

```sql
select owner,
       name,
       type,
       line,
       position,
       text
from all_errors
where owner in ('ORAC', 'ORAC_API', 'ORAC_CODE', 'ORAC_APX_PUB')
order by owner,
         name,
         sequence;
```

Check APEX application metadata:

```sql
select application_id,
       application_name,
       parsing_schema
from apex_applications
order by application_id;
```

Check visible objects for the current user:

```sql
select object_type,
       object_name,
       status
from user_objects
order by object_type,
         object_name;
```
