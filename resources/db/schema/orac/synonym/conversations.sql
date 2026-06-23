--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_conversations context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy conversations access

create or replace synonym orac.conversations for orac_api.conversations_v;

--rollback drop synonym orac.conversations;
