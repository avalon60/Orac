--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Durable removal authorization, checkpoints and outcome; never an installed-plugin inventory.

--changeset clive:create_view_orac_api_plugin_removals_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.plugin_removals_v as
select removal_id,
       plugin_id,
       plugin_registry_id,
       knowledge_scope_id,
       plugin_version,
       manifest_hash,
       schema_disposition,
       database_identity,
       resource_inventory,
       checkpoints,
       external_complete_yn,
       files_complete_yn,
       confirmed_by,
       completed_on,
       last_error_code,
       last_error_message,
       created_on,
       created_by,
       updated_on,
       updated_by,
       row_version
  from orac_core.plugin_removals;
--rollback drop view orac_api.plugin_removals_v;
