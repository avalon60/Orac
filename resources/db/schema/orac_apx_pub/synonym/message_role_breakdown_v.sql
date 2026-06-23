--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_message_role_breakdown_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing message role breakdown view synonym

create or replace synonym orac_apx_pub.message_role_breakdown_v for orac_code.message_role_breakdown_v;

--rollback drop synonym orac_apx_pub.message_role_breakdown_v;
