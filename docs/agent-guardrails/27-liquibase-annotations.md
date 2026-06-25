# Liquibase Annotation Guardrails

## Purpose

This document defines guardrails for Codex agents creating or modifying
Liquibase formatted SQL for Oracle Database installations.

These rules apply to executable database installation scripts, rollback
annotations, preconditions, changelog identifiers, and repository placement.
This document also covers Oracle Database 26ai database object annotations,
where they are installed through Liquibase formatted SQL.

This guidance is adapted from the CoE Liquibase and SQLcl database scripting
cheat sheet and rewritten as enforceable agent guardrails.

Agents must treat Liquibase annotations as executable control logic, not as
comments that can be copied casually.

---

## Core rules

- Every executable Liquibase SQL script must start with `--liquibase formatted sql`.
- Installation scripts must use the `.sql` file extension.
- Use one changeset for each DDL statement or each implicit commit boundary.
- Give every changeset a unique, descriptive `{author}:{id}` identifier.
- Use the requester's login name as the changeset author for new changesets
  unless the repository documents a different approved author convention.
- If a Liquibase SQL file has a script header, use the same resolved login name
  for the `Author:` header line. Do not hard-code a person's display name.
- Do not modify the author of an existing changeset.
- Never use generic changeset ids such as `create_table`, `alter_column`, or `update_object`.
- Do not use `runOnChange:true` for hard objects such as tables, constraints, and indexes.
- Use `runOnChange:true` only for soft objects that are safely created or replaced.
- Use `runAlways:true` only for exceptional pre-install or post-install tasks that must always run.
- Use preconditions for hard-object creation, alteration, and removal.
- Avoid anonymous PL/SQL blocks for DDL orchestration because they are harder to test and do not produce clear Liquibase logs.
- Maintain SQLcl entrypoint scripts and XML controller files as part of the install
  chain, because a correct changeset is not deployable until the controller path
  reaches it in the right order.
- Whenever a Liquibase deployment file changes, perform a front-to-back
  coherence check across every file involved in the affected deployment path.
- Always install and validate the script through Liquibase before considering it proven.

---

## Soft and hard objects

Soft objects can normally be installed with `create or replace`.

Examples:

- package specifications
- package bodies
- views
- synonyms
- grants
- comments
- annotations

Hard objects normally require `create`, `alter`, `drop`, or `revoke`.

Examples:

- tables
- indexes
- primary key constraints
- unique constraints
- foreign key constraints
- check constraints
- column additions, drops, renames, datatype changes, and nullability changes
- grant revocations

Rule:

- Soft objects may use `runOnChange:true` where reapplying the changed definition is safe.
- Hard objects must use separate preconditioned changesets and must not use `runOnChange:true`.

---

## Script file naming

File names should reflect the object name, not the action.

Good:

```text
table/hrs_job_role.sql
index/hrsjr_pk.sql
constraint_pk/hrsjr_pk.sql
view/hrs_job_role_v.sql
package_spec/hrs_job_role_tapi.sql
package_body/hrs_job_role_tapi.sql
```

Avoid:

```text
create_hrs_job_role.sql
alter_hrs_job_role.sql
drop_hrs_job_role.sql
```

Group changesets by the object they maintain unless install ordering requires a reviewed exception.

---

## Changeset naming

The changeset author must normally be the requester's login name in lowercase,
without a domain prefix. When working locally, resolve it from the operating
system login, such as `USERNAME` on Windows or `USER` on Unix-like systems, or
from an explicit repository/user instruction. For example, if the login name is
`cbostock`, use:

```sql
--changeset cbostock:dmt_crop_production_forecast_create stripComments:false
```

If the login name is unavailable and the repository does not define an approved
fallback, ask before inventing a changeset author.

When a new Liquibase SQL file needs the standard script header, use the same
resolved login id in the `Author:` line:

```sql
--liquibase formatted sql
-- Author: cbostock
-- Date: 22-May-2026
-- Description: Creates the DMT crop production forecast table.

--changeset cbostock:dmt_crop_production_forecast_create stripComments:false
```

Do not use a full personal name in the `Author:` line unless the repository
explicitly documents full-name authors as its approved convention.

Do not modify the author of an existing changeset. Existing Liquibase changeset
identifiers are migration history, even if their author does not match the
current requester or the current author convention.

Changeset ids must describe both the action and the object.

Good:

```sql
--changeset cbostock:create_table_hrs_job_role stripComments:false
```

Better where schemas matter:

```sql
--changeset cbostock:create_table_hr_core_hrs_job_role stripComments:false
```

Avoid:

```sql
--changeset cbostock:create_table
--changeset cbostock:hrs_job_role
```

The changeset id must be unique across the full changelog, not just within a file.

---

## Preconditions

Hard-object changesets should use preconditions that make the intended state explicit.

Use:

```sql
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:<value> <query>
```

Rules:

- Use `onFail:MARK_RAN` when the desired end state already exists and the SQL should be skipped.
- Use `onError:HALT` so unexpected dictionary or privilege problems stop the install.
- Write precondition SQL so it returns a simple binary or exact expected value.
- Query Oracle dictionary views directly, such as `all_tables`, `all_tab_columns`, `all_constraints`, `all_indexes`, `all_objects`, or `dba_tab_privs`.
- Make the precondition match the exact object, owner, name, and current state required by the change.
- Do not use vague preconditions that only partially describe the state being changed.

Example create-table precondition:

```sql
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'OWNER' and table_name = 'TABLENAME';
```

Example alter-column precondition:

```sql
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'OWNER' and table_name = 'TABLENAME' and column_name = 'COLUMN1' and data_length = 10;
```

---

## Rollback annotations

Every destructive or structural change should include a rollback annotation unless rollback is intentionally unsupported and documented.

Rules:

- If the changeset creates an object, rollback should drop that object.
- If the changeset alters an object, rollback should alter it back where that is realistically possible.
- If the changeset grants a privilege, rollback should revoke it.
- If the changeset revokes a privilege, rollback should grant it back.
- Do not pretend rollback is harmless when data loss, dependency loss, or changed object state makes it unsafe.
- Comments and annotations normally do not need rollback annotations.

Example:

```sql
--rollback alter table owner.tablename drop constraint tablealias_pk;
```

---

## Package specifications and bodies

Package specs and bodies are soft objects and should normally use `runOnChange:true`.

Use `endDelimiter:/` and put the terminating slash on its own line after the package.

Package spec pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_package_spec_owner_package_name stripComments:false endDelimiter:/ runOnChange:true
create or replace package owner.package_name as
  -- declarations
end package_name;
/
--rollback drop package owner.package_name;
```

Package body pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_package_body_owner_package_name stripComments:false endDelimiter:/ runOnChange:true
create or replace package body owner.package_name as
  -- implementation
end package_name;
/
--rollback drop package body owner.package_name;
```

Rules:

- Keep package specifications and package bodies in separate files or directories.
- Install package specifications before package bodies.
- Do not place package comments before the `create or replace package` line if that would make compiler line numbers harder to use.

---

## Views

Views are soft objects and should normally use `runOnChange:true`.

Pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_view_owner_view_name stripComments:false runOnChange:true
create or replace force view owner.view_name as
select ...
from ...;
--rollback drop view owner.view_name;
```

Rules:

- Use `force` for views so dependency or privilege timing issues do not prevent creation.
- Validate and recompile invalid objects later in the install.
- Consider grants and synonyms that depend on the view.

---

## Synonyms

Synonyms are soft objects and may use `runOnChange:true`.

Pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_synonym_synonymowner_object_name stripComments:false runOnChange:true
create or replace synonym synonymowner.object_name for objectowner.object_name;
--rollback drop synonym synonymowner.object_name;
```

Rules:

- Use owner-qualified object names.
- Use private synonyms unless public synonyms are explicitly approved.
- Consider grants and dependent code before creating or removing synonyms.

---

## Grants and revokes

Grant changesets may use `runOnChange:true` when reapplying the grant is safe.

Pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:grant_read_on_owner_view_name_to_grantee stripComments:false runOnChange:true
grant read on owner.view_name to grantee;
--rollback revoke read on owner.view_name from grantee;
```

Rules:

- Do not combine grants for unrelated objects in one changeset.
- It is acceptable to grant multiple privileges on the same object in one DDL statement.
- Use `read`, not `select`, for read-only grants on `<DOMAIN>_API`
  pass-through views to `<DOMAIN>_CODE`.
- Revokes must be preconditioned because revoking a missing privilege can fail.

Revoke pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:revoke_read_on_owner_view_name_from_grantee stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from dba_tab_privs where owner = 'OWNER' and table_name = 'VIEW_NAME' and grantee = 'GRANTEE' and privilege = 'READ';
revoke read on owner.view_name from grantee;
--rollback grant read on owner.view_name to grantee;
```

---

## Comments

Comments are a limited exception where multiple comment DDL statements may be grouped in one changeset for a single object.

Pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:comment_owner_tablename stripComments:false runOnChange:true
comment on table owner.tablename is 'Purpose of the table.';
comment on column owner.tablename.columnname1 is 'Purpose of the column.';
comment on column owner.tablename.columnname2 is 'Purpose of the column.';
```

Rules:

- Comments do not normally need rollback annotations.
- Keep comments for one object together.
- Remove or update comments when the related object or column is removed or renamed.

---

## Annotations

Oracle Database 26ai database object annotations are table-scoped metadata
scripts in this scaffold and must use `runOnChange:true`. Do not confuse these
database object annotations with Liquibase formatted SQL comments such as
`--changeset`, `--rollback`, or `--preconditions`.

Place table and column annotations for one table in one script under the
`annotation` directory. Name the script after the table:

```text
annotation/<table-name>.sql
```

Pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:<table-name>_annotations stripComments:false runOnChange:true
-- Oracle Database annotation DDL for <table-name> goes here.
```

Rules:

- Install annotation scripts after the related `comment` scripts.
- Keep all annotations for one table together.
- Do not combine annotations for unrelated tables in one script.
- Remove or update annotations when the related table or column is removed or
  renamed.
- Use the normal repository author resolution rules for `<login_name>`.
- Use only documented project annotation names and values. If a task creates or
  changes tables or columns but the required Oracle Database 26ai database
  object annotation vocabulary or values are not available from DDL, comments,
  nearby examples, or explicit requirements, stop and ask for the source of
  truth instead of omitting annotations silently or inventing metadata.
- For semantic annotation rules, including allowed names, value shape, and
  source-of-truth requirements, follow
  `docs/agent-guardrails/20-database-standards.md`.

---

## Tables

Tables are hard objects and must not use `runOnChange:true`.

Create-table pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_table_owner_tablename stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'OWNER' and table_name = 'TABLENAME';
create table owner.tablename
(
  pk_column varchar2(50 char) not null,
  column1 varchar2(256 char) not null,
  row_version number default 0 not null,
  created_by varchar2(255 char) not null,
  created_on timestamp with time zone default current_timestamp not null,
  updated_by varchar2(255 char) not null,
  updated_on timestamp with time zone default current_timestamp not null
)
logging;
--rollback drop table owner.tablename;
```

Rules:

- Add or update the table's row in `table-abbreviations.csv` in the same change
  as a new table changeset, even when constraints and indexes are deferred.
- Only define columns, datatypes, precision, defaults, and nullability in `create table`.
- Do not define primary keys, foreign keys, unique constraints, check constraints, or indexes inside the table creation changeset.
- Put constraints and indexes in their own files and install directories.
- Consider existing data before adding or altering columns.

---

## Constraints

Constraints are hard objects and must not use `runOnChange:true`.

Primary key pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_constraint_tablealias_pk stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'OWNER' and constraint_name = 'TABLEALIAS_PK';
alter table owner.tablename add constraint tablealias_pk
  primary key (pk_column);
--rollback alter table owner.tablename drop constraint tablealias_pk;
```

Foreign key pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_constraint_parent_child_fk1 stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'OWNER' and constraint_name = 'PARENT_CHILD_FK1';
alter table owner.childtablename add constraint parent_child_fk1
  foreign key (child_column1, child_column2)
  references owner.parenttablename(parent_column1, parent_column2);
--rollback alter table owner.childtablename drop constraint parent_child_fk1;
```

Rules:

- Never add constraints inside `create table`.
- Create indexes before primary key and unique constraints where the install sequence expects that.
- Keep primary key, unique, foreign key, and check constraints in the appropriate controller folders.
- Treat constraint definition changes as dependent-object changes, not as simple text edits.
- Prefer creating a new versioned constraint name for changed definitions, such as `fk1` to `fk2`, when that makes validation and preconditions clearer.

---

## Indexes

Indexes are hard objects and must not use `runOnChange:true`.

Unique index pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_index_tablealias_uk1 stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'OWNER' and index_name = 'TABLEALIAS_UK1';
create unique index owner.tablealias_uk1 on owner.tablename (column1 asc) online;
--rollback drop index owner.tablealias_uk1;
```

Non-unique index pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:create_index_tablealias_fk1 stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'OWNER' and index_name = 'TABLEALIAS_FK1';
create index owner.tablealias_fk1 on owner.tablename (column1 asc, column2 desc) online;
--rollback drop index owner.tablealias_fk1;
```

Rules:

- Create unique indexes with the `unique` keyword when they enforce primary key or unique constraint semantics.
- Keep indexes separate from constraints even where names are related.
- Consider performance and locking before adding indexes to large tables.

---

## Column changes

Column changes are hard-object changes and must not use `runOnChange:true`.

Rules:

- Add column changesets to the existing table script when the repository pattern treats them as part of the table object.
- Use preconditions that verify the current column state before altering it.
- Consider existing data before adding not-null columns, reducing precision, changing datatypes, or adding constraints.
- Consider dependent indexes, constraints, packages, views, triggers, grants, and synonyms.
- Use rollback only where the rollback can realistically restore the previous state.

Add-column pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:add_column_tablealias_columnname stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'OWNER' and table_name = 'TABLENAME' and column_name = 'COLUMN2';
alter table owner.tablename add column2 varchar2(30 char);
--rollback alter table owner.tablename drop column column2;
```

Alter-precision pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:alter_column_tablealias_columnname_precision stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'OWNER' and table_name = 'TABLENAME' and column_name = 'COLUMN1' and data_length = 10;
alter table owner.tablename modify column1 varchar2(30 char);
--rollback alter table owner.tablename modify column1 varchar2(10 char);
```

Drop-column pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:drop_column_tablealias_columnname stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'OWNER' and table_name = 'TABLENAME' and column_name = 'COLUMN2';
alter table owner.tablename drop column column2;
--rollback alter table owner.tablename add column2 varchar2(30 char);
```

Rename-column pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:rename_column_tablealias_column2_to_column3 stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'OWNER' and table_name = 'TABLENAME' and column_name = 'COLUMN2';
alter table owner.tablename rename column column2 to column3;
--rollback alter table owner.tablename rename column column3 to column2;
```

---

## Dropping soft objects

When removing a soft object, replace the create changeset with a preconditioned drop changeset in the object file.

Rules:

- Do not create the object and then drop it in the same install path.
- Remove obsolete create changesets from the file.
- Use a precondition so the drop runs only when the object exists.
- Delete no-longer-needed dependent files such as package bodies, grants, and comments.
- Update dependent synonyms, grants, packages, and views.

Drop-view pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:drop_view_owner_view_name stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_objects where owner = 'OWNER' and object_type = 'VIEW' and object_name = 'VIEW_NAME';
drop view owner.view_name;
```

Drop-package pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:drop_package_owner_package_name stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_objects where owner = 'OWNER' and object_type = 'PACKAGE' and object_name = 'PACKAGE_NAME';
drop package owner.package_name;
```

Drop-synonym pattern:

```sql
--liquibase formatted sql
--changeset <login_name>:drop_synonym_owner_synonym_name stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_objects where owner = 'OWNER' and object_type = 'SYNONYM' and object_name = 'SYNONYM_NAME';
drop synonym owner.synonym_name;
```

---

## Destructive changes

Destructive commands require extra scrutiny.

Agents must stop and ask for explicit approval before adding:

- `drop table`
- `drop column`
- `truncate`
- mass `delete`
- broad `revoke`
- object drops that may invalidate application interfaces

Before proposing or applying destructive changes, agents must identify:

- objects that depend on the target
- data that may be lost or transformed
- grants, synonyms, comments, annotations, packages, views, triggers,
  constraints, and indexes affected by the change
- the clean-install path
- the upgrade-from-previous-release path
- the rollback story

---

## Dependent object scenarios

For complex dependent changes, do not improvise a single changeset.

Agents must reason through both:

- clean install from no existing objects
- upgrade from an existing released version with data present

Examples requiring peer review or explicit approval:

- dropping a table
- changing primary key columns
- changing unique constraint columns
- changing foreign key relationships
- renaming columns referenced by code
- moving objects between schemas

When altering a primary key, remember that the primary key usually involves both:

- a primary key index
- a primary key constraint

The install order must handle both objects deliberately.

---

## Repository install sequence

Use the repository's existing controller order. If defining a new Oracle
database install structure, this sequence is a reasonable starting point for a
schema-level controller:

```text
pre_install
privilege
sequence
table
index
constraint_pk
constraint_uk
constraint_other
constraint_fk
temp_table
type_spec
package_spec
view
materialized_view
type_body
package_body
trigger
function
procedure
schedule
job
synonym
grant
role
seed_data
rest_module
comment
annotation
post_install
install_validation
```

Rules:

- Prefer packages over standalone functions and procedures.
- Keep non-production install content separate from production install content.
- Production artifacts should not accidentally include developer-only scripts.
- Use product-level and section-level controller files where the repository pattern requires them.

---

## SQLcl entrypoint scripts

Repositories may use SQLcl entrypoint scripts to launch Liquibase control
files. In Orac, Liquibase-managed schema deployment assets live under
`resources/db/schema` and are copied as a whole into the Oracle container under
`${ORAC_HOME}/schema`. APEX exports live separately under `resources/db/apex`
and must not be included from Liquibase controllers. Keep Liquibase controller
paths relative to the schema root so the same relative paths work before and
after the container copy.

When this pattern is requested or already present, maintain these two
entrypoints from the schema deployment root:

- `install.sql` installs production database and application deliverables only.
- `install_nonprod.sql` runs `install.sql` first, then installs lower
  environment support from the non-production controller.

Production entrypoint pattern:

```sql
prompt ** =================**
prompt ** INSTALL - START **
prompt ** =================**

prompt "... Running the liquibase update.."
liquibase update -changelog-file productController.xml
```

Non-production entrypoint pattern:

```sql
prompt ** =========================**
prompt ** NONPROD INSTALL - START **
prompt ** =========================**

@install.sql

prompt ** =====================**
prompt ** NONPROD - START     **
prompt ** =====================**

liquibase update -changelog-file nonProdController.xml
```

Rules:

- Keep Orac database entrypoint scripts under `resources/db/schema` unless the
  repository documents a different launch location.
- When launching inside the container, run the entrypoint from
  `${ORAC_HOME}/schema` or otherwise preserve the same relative controller
  paths.
- `install_nonprod.sql` must call `@install.sql` before running the nonprod
  controller so lower environments receive the production baseline first.
- Do not include non-production controllers or developer-only scripts from
  `install.sql`.
- If creating these files, include any repository-required SQLcl setup such as
  spooling, timing, `serveroutput`, logging preferences, or screen handling, but
  keep those concerns outside the XML controller files.
- Treat these entrypoints as SQLcl control scripts, not Liquibase formatted SQL
  changeset files.
- If the repository requires script file headers, add them using the
  repository's header convention. For the standard SDK SQL header, resolve the
  `Author:` value from the requester or operating-system login id, not a
  hard-coded personal display name.

---

## XML controller topology

For Orac, the install chain should normally be rooted at `resources/db/schema`
in the repository and at `${ORAC_HOME}/schema` after the container copy:

```text
resources/db/schema/
install.sql
  -> productController.xml
       -> orac_core/schemaController.xml
       -> orac_api/schemaController.xml
       -> orac_code/schemaController.xml
       -> orac_apx_pub/schemaController.xml
       -> orac/schemaController.xml
       -> install_validation/validationController.xml

install_nonprod.sql
  -> install.sql
  -> nonProdController.xml
       -> nonprod/<schema_bundle>/schemaController.xml
       -> nonprod/install_validation/validationController.xml
```

The Orac schema bundle directories are repository-specific schema folders such
as `orac_core`, `orac_api`, `orac_code`, `orac_apx_pub`, `orac`, and
`orac_plugin` when present. Resolve bundle meaning from
`resources/db/schema/AGENT_CONTEXT.md`; do not infer ownership, privileges, or
grant direction from folder names alone.

Do not introduce the generic SDK `product/db/...` or `nonprod/db/...` pathname
shape into Orac unless a task explicitly asks for a directory migration. The
Orac source layout is already the deployment root:
`resources/db/schema/<schema_bundle>/<object_type>/...`.

Rules:

- Use `relativeToChangelogFile="true"` on controller includes.
- Pin controller `xsi:schemaLocation` to the verified SQLcl/Liquibase runtime
  major/minor XSD version. Do not use `dbchangelog-latest.xsd`; it makes
  controller validation non-reproducible across Liquibase upgrades.
- For the current Orac SQLcl Liquibase runtime verified during deployment
  checks, use `dbchangelog-4.30.xsd` in controller examples and generated
  controller files.
- Use `errorIfMissingOrEmpty="false"` for optional `includeAll` directories.
- Include only directories that exist, unless the task explicitly asks to
  instantiate the missing controller structure.
- Where a top-level `install_validation` directory exists, include it after all
  production schema bundle controllers.
- Preserve the repository's established ordering when adding a new include.
- Do not add example-only application or public-schema controller entries just
  because they appeared in another repository.
- Keep production and non-production controller trees separate. Lower
  environment content should live under an explicit non-production subtree such
  as `resources/db/schema/nonprod/...` unless the repository documents another
  separation pattern.

---

## Instantiating a missing control chain

When asked to wire Liquibase deployment controllers into a repository that does
not yet have them, create only the parts needed for the requested scope.

For a production install chain, create or update:

```text
resources/db/schema/install.sql
resources/db/schema/productController.xml
resources/db/schema/<schema_bundle>/schemaController.xml
resources/db/schema/<schema_bundle>/<object_type>/
resources/db/schema/install_validation/validationController.xml
```

For a non-production install chain, create or update:

```text
resources/db/schema/install_nonprod.sql
resources/db/schema/nonProdController.xml
resources/db/schema/nonprod/<schema_bundle>/schemaController.xml
resources/db/schema/nonprod/<schema_bundle>/<object_type>/
resources/db/schema/nonprod/install_validation/validationController.xml
```

Rules:

- Do not create optional validation or non-production directories unless the
  task needs them or the target repository already uses them.
- When an optional directory exists, wire it into the matching top-level
  controller even if it is currently empty and the controller uses
  `errorIfMissingOrEmpty="false"`.
- Derive `<schema_bundle>` directories from
  `resources/db/schema/AGENT_CONTEXT.md` and the existing target repository
  folders.
- When introducing a new schema bundle directory, create its
  `schemaController.xml` in the same change as the first object-type directory
  or SQL file that depends on it.

---

## Top-level product controller

The production controller lives at `resources/db/schema/productController.xml`.
It is the root production Liquibase changelog called by
`resources/db/schema/install.sql`. After the container copy, the same controller
is reached as `${ORAC_HOME}/schema/productController.xml`.

Standard shell:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:ora="http://www.oracle.com/xml/ns/dbchangelog-ext"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd"
>
  <!-- Controller includes go here. -->
</databaseChangeLog>
```

Populate production controller entries from the schema bundle directories under
`resources/db/schema`. Use this order when the matching directories exist:

1. `orac_core/schemaController.xml`
2. `orac_api/schemaController.xml`
3. `orac_code/schemaController.xml`
4. `orac_apx_pub/schemaController.xml`
5. `orac/schemaController.xml`
6. `orac_plugin/schemaController.xml` only when present and in scope
7. `install_validation/validationController.xml` only when present

A production controller with an `install_validation` directory present should
end with `install_validation`. Do not add a `product/db` path layer to Orac's
schema deployment root.

Example:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:ora="http://www.oracle.com/xml/ns/dbchangelog-ext"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd"
>
  <include
    relativeToChangelogFile="true"
    file="orac_core/schemaController.xml"
  />
  <include
    relativeToChangelogFile="true"
    file="orac_api/schemaController.xml"
  />
  <include
    relativeToChangelogFile="true"
    file="orac_code/schemaController.xml"
  />
  <include
    relativeToChangelogFile="true"
    file="orac_apx_pub/schemaController.xml"
  />
  <include
    relativeToChangelogFile="true"
    file="orac/schemaController.xml"
  />
  <include
    relativeToChangelogFile="true"
    file="install_validation/validationController.xml"
  />
</databaseChangeLog>
```

Rules:

- The production schema bundle directories must be wired into
  `productController.xml` in dependency order.
- Keep bundle-level `pre_install` and `post_install` directories inside the
  owning schema bundle and include them from that bundle's
  `schemaController.xml`.
- `install_validation` should normally be included through its
  `validationController.xml`, because validation can have its own internal
  ordering.
- The top-level `install_validation` include must appear after all production
  schema bundle includes.
- Do not include a schema bundle directory directly with `includeAll` from the
  product controller. Include that bundle's `schemaController.xml` so object
  type ordering remains explicit.

---

## Top-level non-production controller

The non-production controller lives at
`resources/db/schema/nonProdController.xml`. It is called only by
`resources/db/schema/install_nonprod.sql`, after `install.sql` has completed.
After the container copy, the same controller is reached as
`${ORAC_HOME}/schema/nonProdController.xml`.

Standard shell:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:ora="http://www.oracle.com/xml/ns/dbchangelog-ext"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd"
>
  <!-- Non-production controller includes go here. -->
</databaseChangeLog>
```

Populate non-production controller entries from lower-environment directories
under `resources/db/schema/nonprod`. Use this order when the matching
directories exist:

1. local environment setup files, such as `development_properties.sql`, when the
   repository uses them
2. `nonprod/_dba` through `includeAll`, only when present
3. `nonprod/pre_install` through `includeAll`, only when present
4. non-production schema bundle controllers such as
   `nonprod/<schema_bundle>/schemaController.xml`
5. non-production application, test, fixture, utility, or data controllers only
   when the directories exist and are in scope
6. `nonprod/post_install` through `includeAll`, only when present
7. `nonprod/install_validation/validationController.xml`, only when present

Rules:

- The common non-production database directories `_dba`, `pre_install`,
  `post_install`, and `install_validation` are optional, but when present they
  must be wired into `nonProdController.xml` in the appropriate place.
- The `install_validation` include must appear after the `post_install`
  include.
- Do not duplicate production schema includes in the non-production controller
  unless those directories actually exist under `resources/db/schema/nonprod`
  and contain non-production changes.
- Never make `install.sql` call `nonProdController.xml`.

---

## Schema/domain controllers

A schema/domain controller lives inside a schema or namespace directory, for
example `resources/db/schema/orac_core/schemaController.xml` or
`resources/db/schema/orac_api/schemaController.xml`. It orders executable SQL
files by object type within that schema bundle. After the container copy, the
same examples resolve under `${ORAC_HOME}/schema`.

Standard shell:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
   xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
   xmlns:ora="http://www.oracle.com/xml/ns/dbchangelog-ext"
   xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd"
>
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="pre_install"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="privilege"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="role"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="sequence"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="table"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="index"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="constraint_pk"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="constraint_uc"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="constraint_other"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="constraint_fk"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="type_spec"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="package_spec"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="view"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="materialized_view"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="type_body"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="package_body"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="trigger"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="context"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="procedure"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="function"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="seed_data"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="schedule"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="job"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="synonym"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="grant"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="rest_module"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="comment"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="annotation"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="post_install"
  />
</databaseChangeLog>
```

Rules:

- Include only object-type directories that exist unless asked to instantiate
  the standard controller shell.
- Do not include Orac-owned APEX export directories in schema controllers; those
  exports live under `resources/db/apex` and are imported by the later APEX
  SQL*Plus setup phase.
- If creating a new schema/domain controller, use Orac's existing object-type
  sequence as the default ordering.
- Directory names vary across repositories. Existing names such as
  `constraint_uc` and `constraint_uk` both mean unique constraints; follow the
  target repository's existing directory name. In Orac, use `constraint_uc`.
- Add new SQL files under the object-type directory that matches the object and
  rely on the schema/domain controller to include that directory.
- Do not place object SQL directly under the schema/domain root when an
  object-type directory exists.

---

## Validation controllers

When top-level `install_validation` exists, prefer a nested validation
controller at `resources/db/schema/install_validation/validationController.xml`.
For non-production validation, use
`resources/db/schema/nonprod/install_validation/validationController.xml`.

Pattern:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:ora="http://www.oracle.com/xml/ns/dbchangelog-ext"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.30.xsd"
>
  <include
    relativeToChangelogFile="true"
    file="pre_validation/schemaController.xml"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="validation"
  />
  <includeAll
    relativeToChangelogFile="true"
    errorIfMissingOrEmpty="false"
    path="post_validation"
  />
</databaseChangeLog>
```

Rules:

- Use a `pre_validation/schemaController.xml` include only when that controller
  exists.
- Put validation SQL under `validation`.
- Put cleanup or post-check SQL under `post_validation`.
- Wire validation from the product or non-production top-level controller only
  when the matching `install_validation` directory exists.

---

## Front-to-back coherence checks

Whenever changing any file involved in a Liquibase based deployment process,
agents must review the affected install path as a connected chain, not as an
isolated file edit.

Scope the check to every file needed to reach, run, and validate the changed
SQL from the relevant entrypoint. Depending on the task, this includes:

- schema deployment SQLcl entrypoints such as `install.sql` and
  `install_nonprod.sql`
- top-level product and non-production XML controllers
- schema/domain XML controllers
- validation controllers
- included object-type directories
- SQL files reached through direct `include` or directory `includeAll` entries
- dependent SQL files that must run before or after the changed file
- rollback, post-install, and install-validation SQL affected by the change

The coherence check must confirm:

- The root entrypoint calls the intended top-level controller.
- The top-level controller includes the correct production or non-production
  Orac schema path, and does not mix production and non-production content.
- Every XML `include` or `includeAll` path resolves relative to its changelog
  file and uses the expected `relativeToChangelogFile` and
  `errorIfMissingOrEmpty` settings for that include style.
- The changed SQL file sits in the object-type directory that matches the
  target object and is reachable through the schema/domain controller.
- Include ordering satisfies object dependencies, such as tables before
  constraints and indexes, package specifications before package bodies, and
  grants or synonyms after the objects they reference.
- Validation SQL, when present, runs after the objects it validates.
- Rollback annotations and destructive changes remain consistent with the
  deployment path and the expected upgrade path.
- The changed file is not orphaned, duplicated through more than one active
  include path, or accidentally excluded by directory placement.

For every SQL file in the affected deployment path, check that Liquibase
formatted SQL directives are well formed and appropriate for the target object
type:

- Executable Liquibase SQL starts with `--liquibase formatted sql`.
- Every executable unit has a `--changeset` line with a stable author, unique
  descriptive id, and only attributes that match the object behavior.
- Soft replaceable objects, such as views, package specifications, package
  bodies, synonyms, grants, comments, and annotations, may use
  `runOnChange:true` when rerunning the statement is safe.
- Hard objects and structural changes, such as tables, constraints, indexes,
  column changes, drops, revokes, and destructive data changes, must not use
  `runOnChange:true`; they need precise preconditions and realistic rollback
  treatment.
- PL/SQL objects that require a slash terminator use the correct
  `endDelimiter:/` directive and place `/` on its own line.
- Hard-object preconditions use `--preconditions` and
  `--precondition-sql-check` directives that match the exact owner, object,
  and state being changed.
- Rollback directives are present where rollback is meaningful, and omitted or
  explicitly documented only where rollback would be misleading or unsafe.
- Comments, SQLcl commands, and Oracle Database object annotations are not
  mistaken for Liquibase control directives.

If the agent cannot inspect the full connected deployment path, it must state
which files or controllers were not checked and why the coherence check is
incomplete.

---

## Validation

Agents must not treat a script as valid merely because the SQL looks correct.

Before declaring the work complete, validate where possible:

- Liquibase parses the formatted SQL annotations.
- A front-to-back coherence check confirms that the changed SQL is reached by
  the intended entrypoint and controller chain.
- The controller includes the script in the intended order.
- The script installs from a clean database state.
- The script upgrades from the last production or baseline release state.
- Existing data does not break the change.
- Liquibase logs show the expected `EXECUTED`, `RERAN`, or `MARK_RAN` states.
- Data dictionary queries confirm the expected end state.
- Invalid objects are recompiled and checked.

If local validation is not available, state that clearly and provide the exact validation that still needs to be run.

---

## Agent checklist

Before editing Liquibase SQL, agents must:

1. Read the relevant database and PL/SQL guardrails.
2. Identify whether the target object is soft or hard.
3. Confirm the correct script location and install sequence.
4. For new changesets, resolve the changeset author from the requester's login
   name or an approved repository convention.
5. Use a unique descriptive changeset id.
6. Add `runOnChange:true` only where the object is safely replaceable.
7. Add precise preconditions for hard-object changes.
8. Add realistic rollback annotations.
9. Consider clean install, upgrade install, and existing data.
10. Consider dependencies and invalidation.
11. Confirm that the controller chain reaches the script in the intended
    production or non-production path.
12. Perform a front-to-back coherence check across the affected entrypoints,
    controllers, SQL files, rollback logic, and validation files.
13. Confirm every SQL file in that path has well formed Liquibase directives
    appropriate for its target object type.
14. Validate through Liquibase where possible.

If any of these cannot be satisfied, the agent must explain the gap before continuing.
