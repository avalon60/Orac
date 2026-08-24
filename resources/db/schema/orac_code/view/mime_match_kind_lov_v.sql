--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes active MIME_MATCH_KIND values through the stable LOV contract.

--changeset clive:create_view_orac_code_mime_match_kind_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.mime_match_kind_lov_v as
select mime_match_kind_code return_value
     , display_value
     , description
     , display_sequence
     , icon
     , color
  from orac_code.mime_match_kind_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y';
--rollback drop view orac_code.mime_match_kind_lov_v;

