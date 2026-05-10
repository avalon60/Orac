---
name: oracle-sqlcl
description: Use SQLcl MCP or host SQLcl to inspect and verify an Oracle development database safely when checking schemas, objects, constraints, grants, package status, data shape, imports, deployments, or database errors.
---

# Oracle SQLcl Database Access

Use the configured SQLcl MCP server for lightweight inspection of the current project's Oracle development database.

Use `saved_connections.csv` in this skill directory as the project-maintained registry of host SQLcl saved connections.

SQLcl MCP is useful for read-only checks, metadata inspection, object lookups, and quick verification. However, the SQLcl MCP transport can occasionally disconnect or become unreliable. When that happens, use host `SQLcl` with one of the project's saved connections as the fallback.

In Codex, host `SQLcl` may still be unable to reach the database from the default sandboxed shell. If a saved connection fails with a network adapter error such as `ORA-17820`, rerun the host `SQLcl` command with escalated permissions so it executes outside the sandbox.

## Preferred Access Order

1. Use SQLcl MCP for lightweight read-only database inspection.
2. If SQLcl MCP disconnects, fails, hangs, or returns inconsistent results, retry once.
3. If it fails again, use host `SQLcl` with the saved connection selected from `saved_connections.csv` for the required role.
4. If host `SQLcl` cannot connect from the sandbox, rerun it with escalated permissions.
5. Use host `SQLcl` for critical post-operation verification.

## Saved Connection Registry

Use `saved_connections.csv` to resolve project-specific saved connection names.

The file must contain these headers:

```csv
Saved Connection,Role,Description
```

Projects maintain the rows.

The exact saved connection names are project-specific. Do not assume that one project's connection names apply to another.

Select connections by `Role`, not by hardcoded connection name.

Typical roles may include:

```text
app    - least-privileged application, consumer, or verification schema
owner  - domain owner or deployment schema, used only when required
admin  - elevated administrative connection, used only when genuinely required
apex   - optional APEX parsing or public schema, only for projects that use APEX
```

Prefer the least-privileged role that can answer the question.

Use the row with role `app` for normal object checks visible to the runtime schema.

Use the row with role `apex` only when checking objects visible to an APEX application in a project that actually uses APEX.

Use the row with role `owner` or `admin` only when elevated privileges are genuinely required, such as checking cross-schema grants, invalid objects across schemas, container-level metadata, or installation issues.

If multiple rows fit the role, use `Description` to select the narrowest suitable connection.

If `saved_connections.csv` is empty, missing, or does not define a suitable role, continue with SQLcl MCP where possible. If host `SQLcl` fallback is required, stop and ask the user which saved connection should be used.

Where the project follows the standard least-privilege schema topology, respect the boundaries between `<DOMAIN>_CORE`, `<DOMAIN>_API`, `<DOMAIN>_CODE`, and any `<DOMAIN>_<CONSUMER>_PUB` schemas.

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

When SQLcl MCP is unreliable, use host `SQLcl` with the connection resolved from `saved_connections.csv`.

In Codex, prefer treating host `SQLcl` as a two-step fallback:

1. Try the saved connection normally.
2. If the connection fails with a network or socket error such as `ORA-17820`, rerun the same command with escalated permissions.

Use this bash pattern:

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

Replace `<saved_connection_name>` with the `Saved Connection` value from `saved_connections.csv` for the selected role.

Prefer host `SQLcl` fallback for:

- verifying installation or deployment results
- checking invalid objects after install scripts
- checking package compilation errors after deployment
- confirming critical DDL or DML effects
- diagnosing failures where SQLcl MCP transport disconnected
- checking optional APEX imports where the project uses APEX

When using the fallback:

- prefer the least-privileged saved connection that can answer the question
- resolve the connection from `saved_connections.csv` by `Role`
- use the normal application or consumer role for routine checks
- use an APEX-specific role only for APEX projects and only when needed
- use owner or admin roles only when elevated access is genuinely required
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

Check package errors for the current user:

```sql
select name,
       type,
       line,
       position,
       text
from user_errors
order by name,
         type,
         sequence;
```

Check package errors across project schemas.

Replace the schema placeholders with the relevant schema names for the current project:

```sql
select owner,
       name,
       type,
       line,
       position,
       text
from all_errors
where owner in (
         '<DOMAIN>_API',
         '<DOMAIN>_CODE',
         '<DOMAIN>_<CONSUMER>_PUB'
      )
order by owner,
         name,
         sequence;
```

If the project uses APEX, check APEX application metadata:

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
