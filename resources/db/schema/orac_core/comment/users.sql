--liquibase formatted sql

--changeset clive:comment_orac_core_comment_users context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.users is
  'Stores registered users of the orac system.'
;

comment on column orac_core.users.user_id is
  'Primary key for the orac_core.users table.'
;

comment on column orac_core.users.username is
  'Unique login handle for the orac_core.users table.'
;

comment on column orac_core.users.display_name is
  'Human-friendly name for the user.'
;

comment on column orac_core.users.email is
  'Primary contact email for the user.'
;
