--liquibase formatted sql

--changeset clive:drop_box_grant_drop_box_api_to_orac_plugin context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
grant execute on orac_dropbox.drop_box_api to orac_plugin
;
