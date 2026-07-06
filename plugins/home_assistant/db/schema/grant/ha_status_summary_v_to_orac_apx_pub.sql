--liquibase formatted sql

--changeset cbostock:home_assistant_grant_ha_status_summary_v_to_orac_apx_pub context:plugin,prod labels:plugin,home_assistant stripComments:false runOnChange:true
grant select on orac_ha.ha_status_summary_v to orac_apx_pub
;
