--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_messages_per_day_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: internal daily messages view synonym

create or replace synonym orac.messages_per_day_v for orac_code.messages_per_day_v;

--rollback drop synonym orac.messages_per_day_v;
