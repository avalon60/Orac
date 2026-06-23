--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_user_preferences context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy user preferences access

create or replace synonym orac.user_preferences for orac_api.user_preferences_v;

--rollback drop synonym orac.user_preferences;
