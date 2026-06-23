--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_preference_definitions context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy preference definition access

create or replace synonym orac.preference_definitions for orac_api.preference_definitions_v;

--rollback drop synonym orac.preference_definitions;
