--liquibase formatted sql

--changeset clive:grant_orac_dropbox_drop_processing_profile_lov_v_to_orac_apx_pub context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: grants Drop Box processing profile LOV to APEX admin schema

grant read on orac_dropbox.drop_processing_profile_lov_v to orac_apx_pub;

--rollback revoke read on orac_dropbox.drop_processing_profile_lov_v from orac_apx_pub;
