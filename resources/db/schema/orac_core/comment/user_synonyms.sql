--liquibase formatted sql

--changeset clive:comment_orac_core_user_synonyms context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.user_synonyms is
  'Associates alternate identity values with an Orac user.';
comment on column orac_core.user_synonyms.user_id is
  'User identified by the alternate value.';
comment on column orac_core.user_synonyms.user_alias_type_domain_code is
  'Fixed USER_ALIAS_TYPE reference domain for the alternate identity.';
comment on column orac_core.user_synonyms.user_alias_type_ref_value_code is
  'Type of alternate identity value.';
comment on column orac_core.user_synonyms.alias_value is
  'Alternate identity value for the user.';
comment on column orac_core.user_synonyms.is_active is
  'Indicates whether the alternate identity remains active.';
