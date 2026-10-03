--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Validates the current plugin registration scope association.

--changeset clive:create_trigger_orac_api_plgreg_bi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_api.plgreg_bi
before insert on orac_core.plugin_registry
for each row
declare
  l_scope orac_api.knowledge_scopes_v%rowtype;
begin
  select * into l_scope
    from orac_api.knowledge_scopes_v
   where knowledge_scope_id = :new.knowledge_scope_id;
  if l_scope.scope_type <> 'PLUGIN'
     or l_scope.plugin_id is null
     or l_scope.plugin_id <> :new.plugin_id
     or l_scope.retired_on is not null
  then
    raise_application_error(-20047, 'Current registration requires its own non-retired plugin scope.');
  end if;
exception
  when no_data_found then
    raise_application_error(-20047, 'Current registration scope does not exist.');
end;
/
--rollback drop trigger orac_api.plgreg_bi;
