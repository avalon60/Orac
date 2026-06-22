--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_users context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing users synonym

create or replace synonym orac_apx_pub.users for orac_api.users;

--rollback drop synonym orac_apx_pub.users;
