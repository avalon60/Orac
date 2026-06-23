--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_user_synonyms context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy user synonym access

create or replace synonym orac.user_synonyms for orac_api.user_synonyms_v;

--rollback drop synonym orac.user_synonyms;
