--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_ingestion_events_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_ingestion_events_v as
select ingestion_event_id,
       ingestion_request_id,
       event_type,
       event_message,
       event_ts,
       created_by,
       created_on
  from orac_core.knowledge_ingestion_events;
--rollback drop view orac_api.knowledge_ingestion_events_v;
