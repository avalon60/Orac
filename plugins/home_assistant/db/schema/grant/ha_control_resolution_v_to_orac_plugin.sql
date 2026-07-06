--liquibase formatted sql

--changeset cbostock:home_assistant_grant_ha_control_resolution_v_to_orac_plugin context:plugin,prod labels:plugin,home_assistant stripComments:false runOnChange:true
grant select on orac_ha.ha_control_resolution_v to orac_plugin
;
