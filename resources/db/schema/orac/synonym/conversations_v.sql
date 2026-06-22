--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_conversations_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: compatibility synonym for the new conversations surface

create or replace synonym orac.conversations_v for orac_api.conversations_v;

--rollback drop synonym orac.conversations_v;
