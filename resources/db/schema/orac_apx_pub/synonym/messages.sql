--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_messages context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing legacy synonym for messages

create or replace synonym orac_apx_pub.messages for orac_api.messages_v;

--rollback drop synonym orac_apx_pub.messages;
