--liquibase formatted sql

--changeset clive:create_view_orac_code_timezone_lov_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-08-08
-- __description__: active curated timezone selector values

create or replace force view orac_code.timezone_lov_v as
select timezone_code return_value
     , display_value
     , description
     , display_sequence
     , icon
     , color
  from orac_code.timezone_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y'
   and timezone_group_domain_active_yn = 'Y'
   and timezone_group_active_yn = 'Y';

--rollback drop view orac_code.timezone_lov_v;
