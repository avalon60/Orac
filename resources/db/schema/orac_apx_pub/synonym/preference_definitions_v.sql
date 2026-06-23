--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_preference_definitions_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: public-facing preference definitions synonym

create or replace synonym orac_apx_pub.preference_definitions_v for orac_api.preference_definitions_v;

--rollback drop synonym orac_apx_pub.preference_definitions_v;
