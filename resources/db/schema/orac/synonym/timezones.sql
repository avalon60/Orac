--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_timezones context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy timezone access

create or replace synonym orac.timezones for orac_api.timezones_v;

--rollback drop synonym orac.timezones;
