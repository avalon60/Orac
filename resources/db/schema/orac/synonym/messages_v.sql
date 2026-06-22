--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_messages_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: compatibility synonym for the new messages surface

create or replace synonym orac.messages_v for orac_api.messages_v;

--rollback drop synonym orac.messages_v;
