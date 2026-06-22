--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_user_synonyms_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: compatibility synonym for the new user synonyms surface

create or replace synonym orac.user_synonyms_v for orac_api.user_synonyms_v;

--rollback drop synonym orac.user_synonyms_v;
