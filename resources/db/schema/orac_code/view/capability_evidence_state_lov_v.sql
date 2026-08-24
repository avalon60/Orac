--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes active CAPABILITY_EVIDENCE_STATE values through the stable LOV contract.

--changeset clive:create_view_orac_code_capability_evidence_state_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.capability_evidence_state_lov_v as
select capability_evidence_state_code return_value
     , display_value
     , description
     , display_sequence
     , icon
     , color
  from orac_code.capability_evidence_state_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y';
--rollback drop view orac_code.capability_evidence_state_lov_v;

