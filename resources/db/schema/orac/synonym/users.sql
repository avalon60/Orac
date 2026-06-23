--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_users context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy users access

create or replace synonym orac.users for orac_api.users;

--rollback drop synonym orac.users;
