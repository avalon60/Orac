--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Controlled API access to plugin_removals.

--changeset clive:grant_plugin_removals_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update on orac_core.plugin_removals to orac_api with grant option;
--rollback revoke select, insert, update on orac_core.plugin_removals from orac_api;
