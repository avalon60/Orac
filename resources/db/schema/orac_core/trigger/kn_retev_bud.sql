--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Protects append-only knowledge retrieval audit events.

--changeset clive:create_trigger_orac_core_kn_retev_bud context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_retev_bud
before update or delete on orac_core.knowledge_retrieval_events
begin
  raise_application_error(-20630, 'Knowledge retrieval audit events are append-only.');
end;
/
--rollback drop trigger orac_core.kn_retev_bud;
