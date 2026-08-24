--liquibase formatted sql

--changeset clive:create_view_orac_api_domain_ref_values_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: read-only API projection of reference-domain values

create or replace force view orac_api.domain_ref_values_v as
select domain_code
     , ref_value_code
     , parent_domain_code
     , parent_ref_value_code
     , display_value
     , description
     , display_sequence
     , icon
     , color
     , active_yn
     , system_required_yn
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.domain_ref_values;

--rollback drop view orac_api.domain_ref_values_v;
