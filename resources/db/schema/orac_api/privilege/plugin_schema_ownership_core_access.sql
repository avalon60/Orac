--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Controlled API access to plugin_schema_ownership.

--changeset clive:grant_plugin_schema_ownership_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update on orac_core.plugin_schema_ownership to orac_api with grant option;
--rollback revoke select, insert, update on orac_core.plugin_schema_ownership from orac_api;
