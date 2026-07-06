--liquibase formatted sql

--changeset clive:drop_box_grant_drop_location_runtime_v_to_orac_plugin context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
grant select on orac_dropbox.drop_location_runtime_v to orac_plugin
;
