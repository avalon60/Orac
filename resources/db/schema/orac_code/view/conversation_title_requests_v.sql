--liquibase formatted sql
--changeset clive:create_view_orac_code_conversation_title_requests_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.conversation_title_requests_v as
select * from orac_api.conversation_title_requests_v;
--rollback drop view orac_code.conversation_title_requests_v;
