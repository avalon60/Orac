--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Privileged provisioning receipts for dedicated plugin schema incarnations; name matching alone is not ownership.

--changeset clive:comment_plugin_schema_ownership context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.plugin_schema_ownership is 'Privileged provisioning receipts for dedicated plugin schema incarnations; name matching alone is not ownership.';
comment on column orac_core.plugin_schema_ownership.schema_ownership_id is 'Receipt surrogate key.';
comment on column orac_core.plugin_schema_ownership.plugin_id is 'Verified logical plugin owner.';
comment on column orac_core.plugin_schema_ownership.plugin_registry_id is 'Provisioning registration snapshot; deliberately no registry foreign key.';
comment on column orac_core.plugin_schema_ownership.database_identity is 'Immutable database and PDB target evidence.';
comment on column orac_core.plugin_schema_ownership.schema_name is 'Dedicated schema from validated host-managed manifest metadata.';
comment on column orac_core.plugin_schema_ownership.database_user_id is 'Oracle user identity captured immediately after privileged creation.';
comment on column orac_core.plugin_schema_ownership.database_user_created_on is 'User creation evidence; prevents adopting a recreated same-name user.';
comment on column orac_core.plugin_schema_ownership.disposition is 'OWNED, RETAINED or DROPPED; retained schemas are not adoptable by ordinary install.';
comment on column orac_core.plugin_schema_ownership.removal_id is 'Removal operation reference snapshot.';
comment on column orac_core.plugin_schema_ownership.provisioning_evidence is 'Credential-free host provisioning provenance; runtime callers cannot attest ownership.';
comment on column orac_core.plugin_schema_ownership.created_on is 'Receipt creation time.';
comment on column orac_core.plugin_schema_ownership.created_by is 'Database actor.';
comment on column orac_core.plugin_schema_ownership.updated_on is 'Last update time.';
comment on column orac_core.plugin_schema_ownership.updated_by is 'Last database actor.';
comment on column orac_core.plugin_schema_ownership.row_version is 'Optimistic concurrency version.';
