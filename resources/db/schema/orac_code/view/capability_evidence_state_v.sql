--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the CAPABILITY_EVIDENCE_STATE reference domain through Code.

--changeset clive:create_view_orac_code_capability_evidence_state_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.capability_evidence_state_v as
select ref.ref_value_code capability_evidence_state_code
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
 where dom.domain_code = 'CAPABILITY_EVIDENCE_STATE';
--rollback drop view orac_code.capability_evidence_state_v;

