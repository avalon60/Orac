--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Durable removal authorization, checkpoints and outcome; never an installed-plugin inventory.

--changeset clive:comment_plugin_removals context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.plugin_removals is 'Durable removal authorization, checkpoints and outcome; never an installed-plugin inventory.';
comment on column orac_core.plugin_removals.removal_id is 'Host-generated immutable operation identifier.';
comment on column orac_core.plugin_removals.plugin_id is 'Logical plugin name at authorization time.';
comment on column orac_core.plugin_removals.plugin_registry_id is 'Expected current registry key snapshot; deliberately not a foreign key.';
comment on column orac_core.plugin_removals.knowledge_scope_id is 'Immutable historical domain identifier captured at authorization.';
comment on column orac_core.plugin_removals.plugin_version is 'Authorized version snapshot.';
comment on column orac_core.plugin_removals.manifest_hash is 'Authorized installed manifest fingerprint.';
comment on column orac_core.plugin_removals.schema_disposition is 'DROP or KEEP; cannot change on retry.';
comment on column orac_core.plugin_removals.database_identity is 'Authorized database and PDB identity.';
comment on column orac_core.plugin_removals.resource_inventory is 'Bounded, credential-free authorized schema, application and managed path inventory.';
comment on column orac_core.plugin_removals.checkpoints is 'Verified per-resource completion results; no secrets or executable commands.';
comment on column orac_core.plugin_removals.external_complete_yn is 'All verified external database and APEX resources have been handled.';
comment on column orac_core.plugin_removals.files_complete_yn is 'All mandatory configuration, secret and managed file cleanup has completed.';
comment on column orac_core.plugin_removals.confirmed_by is 'Actor explicitly authorizing the bounded removal.';
comment on column orac_core.plugin_removals.completed_on is 'Final Core transaction completion; null fences the current installation.';
comment on column orac_core.plugin_removals.last_error_code is 'Sanitized retry diagnostic code.';
comment on column orac_core.plugin_removals.last_error_message is 'Sanitized retry diagnostic summary.';
comment on column orac_core.plugin_removals.created_on is 'Receipt creation time.';
comment on column orac_core.plugin_removals.created_by is 'Database actor.';
comment on column orac_core.plugin_removals.updated_on is 'Last update time.';
comment on column orac_core.plugin_removals.updated_by is 'Last database actor.';
comment on column orac_core.plugin_removals.row_version is 'Optimistic concurrency version.';
