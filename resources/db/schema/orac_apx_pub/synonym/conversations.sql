--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_conversations context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing legacy synonym for conversations

create or replace synonym orac_apx_pub.conversations for orac_api.conversations_v;

--rollback drop synonym orac_apx_pub.conversations;
