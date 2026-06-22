--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_orac_personalities context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy personality access

create or replace synonym orac.orac_personalities for orac_api.orac_personalities_v;

--rollback drop synonym orac.orac_personalities;
