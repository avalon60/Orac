--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Privileged provisioning receipts for dedicated plugin schema incarnations; name matching alone is not ownership.

--changeset clive:create_view_orac_api_plugin_schema_ownership_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.plugin_schema_ownership_v as
select schema_ownership_id,
       plugin_id,
       plugin_registry_id,
       database_identity,
       schema_name,
       database_user_id,
       database_user_created_on,
       disposition,
       removal_id,
       provisioning_evidence,
       created_on,
       created_by,
       updated_on,
       updated_by,
       row_version
  from orac_core.plugin_schema_ownership;
--rollback drop view orac_api.plugin_schema_ownership_v;
