--liquibase formatted sql

--changeset cbostock:home_assistant_grant_ha_sync_api_to_orac_plugin context:plugin,prod labels:plugin,home_assistant stripComments:false runOnChange:true
grant execute on orac_ha.ha_sync_api to orac_plugin
;
