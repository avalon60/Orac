--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Read-only business layer access to plugin_removals.

--changeset clive:grant_plugin_removals_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.plugin_removals_v to orac_code with grant option;
--rollback revoke read on orac_api.plugin_removals_v from orac_code;
