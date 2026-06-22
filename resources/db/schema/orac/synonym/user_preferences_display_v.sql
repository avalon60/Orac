--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_user_preferences_display_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: internal user preferences display view synonym

create or replace synonym orac.user_preferences_display_v for orac_code.user_preferences_display_v;

--rollback drop synonym orac.user_preferences_display_v;
