--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_user_preferences_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing user preferences maintenance synonym

create or replace synonym orac_apx_pub.user_preferences_v for orac_code.user_preferences_v;

--rollback drop synonym orac_apx_pub.user_preferences_v;
