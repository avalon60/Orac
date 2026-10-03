--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Classifies plugin_schema_ownership identifiers.

--changeset clive:annotate_plugin_schema_ownership context:core labels:core stripComments:false runOnChange:true
alter table orac_core.plugin_schema_ownership modify schema_ownership_id annotations (add if not exists semantic_role 'primary_key');
alter table orac_core.plugin_schema_ownership modify plugin_registry_id annotations (add if not exists semantic_role 'logical_reference');
