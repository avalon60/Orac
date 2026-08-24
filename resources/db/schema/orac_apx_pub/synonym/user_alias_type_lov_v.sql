--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_user_alias_type_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace synonym orac_apx_pub.user_alias_type_lov_v
  for orac_code.user_alias_type_lov_v;
--rollback drop synonym orac_apx_pub.user_alias_type_lov_v;
