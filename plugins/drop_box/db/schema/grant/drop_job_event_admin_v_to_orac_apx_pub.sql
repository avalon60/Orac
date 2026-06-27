--liquibase formatted sql

--changeset clive:grant_orac_dropbox_drop_job_event_admin_v_to_orac_apx_pub context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: grant drop-box admin job event view to APEX access schema

grant read on orac_dropbox.drop_job_event_admin_v to orac_apx_pub;

--rollback revoke read on orac_dropbox.drop_job_event_admin_v from orac_apx_pub;
