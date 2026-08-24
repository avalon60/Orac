--liquibase formatted sql

--changeset clive:create_view_orac_code_pref_control_type_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.pref_control_type_lov_v as
select pref_control_type_code return_value,
       display_value,
       description,
       display_sequence,
       icon,
       color
  from orac_code.pref_control_type_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y';
--rollback drop view orac_code.pref_control_type_lov_v;
