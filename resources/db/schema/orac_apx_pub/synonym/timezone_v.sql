--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_timezone_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: APEX-facing synonym for curated timezone semantics

create or replace synonym orac_apx_pub.timezone_v for orac_code.timezone_v;

--rollback drop synonym orac_apx_pub.timezone_v;
