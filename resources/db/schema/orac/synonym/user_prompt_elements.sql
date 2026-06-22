--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_user_prompt_elements context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy user prompt element access

create or replace synonym orac.user_prompt_elements for orac_api.user_prompt_elements_v;

--rollback drop synonym orac.user_prompt_elements;
