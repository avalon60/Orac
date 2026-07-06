--liquibase formatted sql

--changeset clive:drop_box_comment_drop_processing_profile context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
comment on table orac_dropbox.drop_processing_profile is 'Named ingestion recipes available to drop-box locations.'
;
comment on column orac_dropbox.drop_processing_profile.profile_code is 'Stable lowercase processing profile code selected by drop locations and copied onto queued jobs.'
;
comment on column orac_dropbox.drop_processing_profile.default_instruction is 'Default recipe instruction snapshotted onto queued jobs at enqueue time.'
;
comment on column orac_dropbox.drop_processing_profile.active_yn is 'Y when the profile may be selected and used by enabled drop locations.'
;
comment on column orac_dropbox.drop_processing_profile.system_yn is 'Y for system-seeded profiles maintained by the plugin payload.'
;
comment on column orac_dropbox.drop_processing_profile.created_on is 'Orac local row creation timestamp maintained by drp_prf_biu.'
;
comment on column orac_dropbox.drop_processing_profile.updated_on is 'Orac local row update timestamp maintained by drp_prf_biu.'
;
comment on column orac_dropbox.drop_processing_profile.row_version is 'Optimistic locking value maintained by drp_prf_biu.'
;
