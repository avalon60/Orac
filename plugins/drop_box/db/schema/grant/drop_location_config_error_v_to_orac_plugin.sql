--liquibase formatted sql

--changeset clive:grant_orac_dropbox_view_drop_location_config_error_v_to_orac_plugin context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: allow plugin runtime to log drop-location configuration errors

grant select on orac_dropbox.drop_location_config_error_v to orac_plugin;

--rollback revoke select on orac_dropbox.drop_location_config_error_v from orac_plugin;
