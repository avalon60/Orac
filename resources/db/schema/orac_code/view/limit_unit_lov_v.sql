--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes active LIMIT_UNIT values through the stable LOV contract.

--changeset clive:create_view_orac_code_limit_unit_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.limit_unit_lov_v as
select limit_unit_code return_value
     , display_value
     , description
     , display_sequence
     , icon
     , color
  from orac_code.limit_unit_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y';
--rollback drop view orac_code.limit_unit_lov_v;

