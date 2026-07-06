--liquibase formatted sql

--changeset clive:grant_orac_dropbox_drop_box_admin_api_to_orac_apx_pub context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: grant drop-box admin write API to APEX access schema

grant execute on orac_dropbox.drop_box_admin_api to orac_apx_pub;

--rollback revoke execute on orac_dropbox.drop_box_admin_api from orac_apx_pub;
