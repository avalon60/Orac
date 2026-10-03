--liquibase formatted sql

--changeset clive:create_package_body_orac_api_knowledge_scopes_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: controlled insert API body for canonical knowledge scopes
create or replace package body orac_api.knowledge_scopes_tapi
as
  procedure ins(p_row in out orac_api.knowledge_scopes_v%rowtype)
  is
  begin
    insert into orac_api.knowledge_scopes_v
      (scope_type, project_id, plugin_id)
    values
      (p_row.scope_type, p_row.project_id, p_row.plugin_id)
    returning knowledge_scope_id, row_version
         into p_row.knowledge_scope_id, p_row.row_version;
  end ins;
  procedure retire_for_removal(p_removal_id in varchar2) is
    l_removal orac_api.plugin_removals_v%rowtype;
  begin
    select * into l_removal from orac_api.plugin_removals_v
     where removal_id = p_removal_id and completed_on is null
       and external_complete_yn = 'Y' and files_complete_yn = 'Y';
    update orac_api.knowledge_scopes_v
       set retired_on = systimestamp
     where knowledge_scope_id = l_removal.knowledge_scope_id
       and scope_type = 'PLUGIN' and plugin_id = l_removal.plugin_id
       and retired_on is null;
    if sql%rowcount <> 1
    then
      raise_application_error(-20074, 'Removal scope ownership is inconsistent.');
    end if;
    insert into orac_api.knowledge_ingestion_events_v
      (ingestion_request_id, event_type, event_message)
    select req.ingestion_request_id, 'scope_retired', 'Target plugin scope was retired.'
      from orac_api.knowledge_ingestion_requests_v req
      join orac_api.knowledge_source_objects_v src on src.source_object_id = req.source_object_id
     where src.knowledge_scope_id = l_removal.knowledge_scope_id
       and req.status_code in ('QUEUED', 'PROCESSING', 'RETRY_WAIT');
    update orac_api.knowledge_ingestion_requests_v req
       set status_code = 'FAILED', stage_code = 'FAILED',
           lease_owner = null, lease_token = null, lease_expires_on = null,
           last_error_code = 'SCOPE_RETIRED',
           last_error_message = 'Target plugin scope was retired.'
     where req.status_code in ('QUEUED', 'PROCESSING', 'RETRY_WAIT')
       and exists (
         select 1 from orac_api.knowledge_source_objects_v src
          where src.source_object_id = req.source_object_id
            and src.knowledge_scope_id = l_removal.knowledge_scope_id
       );
  end retire_for_removal;
end knowledge_scopes_tapi;
/
--rollback drop package body orac_api.knowledge_scopes_tapi;
