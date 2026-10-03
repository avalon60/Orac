--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:grant_plugin_removals_tapi_to_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.plugin_removals_tapi to orac_code;
--rollback revoke execute on orac_api.plugin_removals_tapi from orac_code;
