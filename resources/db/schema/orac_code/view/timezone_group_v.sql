--liquibase formatted sql

--changeset clive:create_view_orac_code_timezone_group_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: semantic projection of timezone grouping reference values

create or replace force view orac_code.timezone_group_v as
select ref.ref_value_code timezone_group_code
     , ref.display_value
     , ref.description
     , ref.display_sequence
     , ref.icon
     , ref.color
     , dom.active_yn domain_active_yn
     , ref.active_yn
     , ref.system_required_yn
  from orac_api.domain_codes_v dom
  join orac_api.domain_ref_values_v ref
    on ref.domain_code = dom.domain_code
 where dom.domain_code = 'TIMEZONE_GROUP';

--rollback drop view orac_code.timezone_group_v;
