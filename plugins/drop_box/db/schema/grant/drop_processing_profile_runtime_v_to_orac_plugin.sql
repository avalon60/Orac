--liquibase formatted sql

--changeset clive:grant_orac_dropbox_drop_processing_profile_runtime_v_to_orac_plugin context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: grants active Drop Box processing profiles to Orac plugin bridge

grant select on orac_dropbox.drop_processing_profile_runtime_v to orac_plugin;

--rollback revoke select on orac_dropbox.drop_processing_profile_runtime_v from orac_plugin;
