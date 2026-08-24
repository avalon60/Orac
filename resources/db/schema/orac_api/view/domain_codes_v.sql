--liquibase formatted sql

--changeset clive:create_view_orac_api_domain_codes_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: read-only API projection of reference-data domains

create or replace force view orac_api.domain_codes_v as
select domain_code
     , display_name
     , description
     , active_yn
     , system_required_yn
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.domain_codes;

--rollback drop view orac_api.domain_codes_v;
