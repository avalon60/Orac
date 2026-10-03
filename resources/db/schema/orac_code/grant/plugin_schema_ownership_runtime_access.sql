--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Privileged schema provisioning and removal receipts.

--changeset clive:grant_plugin_schema_ownership_v_to_orac context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_schema_ownership_v to orac;
--rollback revoke read on orac_code.plugin_schema_ownership_v from orac;
