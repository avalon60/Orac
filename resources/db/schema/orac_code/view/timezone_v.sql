--liquibase formatted sql

--changeset clive:create_view_orac_code_timezone_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: semantic projection of curated timezone values and their groups

create or replace force view orac_code.timezone_v as
select ref.ref_value_code timezone_code
     , ref.display_value
     , ref.description
     , ref.display_sequence
     , ref.icon
     , ref.color
     , dom.active_yn domain_active_yn
     , ref.active_yn
     , ref.system_required_yn
     , grp.ref_value_code timezone_group_code
     , grp.display_value timezone_group_display_value
     , grp.display_sequence timezone_group_display_sequence
     , grp_dom.active_yn timezone_group_domain_active_yn
     , grp.active_yn timezone_group_active_yn
  from orac_api.domain_codes_v dom
  join orac_api.domain_ref_values_v ref
    on ref.domain_code = dom.domain_code
  join orac_api.domain_codes_v grp_dom
    on grp_dom.domain_code = ref.parent_domain_code
  join orac_api.domain_ref_values_v grp
    on grp.domain_code = ref.parent_domain_code
   and grp.ref_value_code = ref.parent_ref_value_code
 where dom.domain_code = 'TIMEZONE'
   and ref.parent_domain_code = 'TIMEZONE_GROUP';

--rollback drop view orac_code.timezone_v;
