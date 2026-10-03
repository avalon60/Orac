--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Classifies plugin_removals identifiers.

--changeset clive:annotate_plugin_removals context:core labels:core stripComments:false runOnChange:true
alter table orac_core.plugin_removals modify removal_id annotations (add if not exists semantic_role 'primary_key');
alter table orac_core.plugin_removals modify plugin_registry_id annotations (add if not exists semantic_role 'logical_reference');
