--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_code_package_body_relational_query_worker_api context:core labels:core,relational_query stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package body orac_code.relational_query_worker_api as
  procedure sync_dataset(p_dataset_id in varchar2, p_plugin_id in varchar2, p_metadata_version in varchar2,
                         p_manifest_hash in varchar2, p_declaration in clob) is
  begin
    if p_declaration is not json or p_dataset_id not like p_plugin_id || '.%'
    then
      raise_application_error(-20820, 'QUERY_DECLARATION_INVALID');
    end if;
    merge into orac_api.relational_query_catalogue_v dst
    using (select p_dataset_id dataset_id from dual) src on (dst.dataset_id=src.dataset_id)
    when matched then update set
      verified_yn = case when dst.manifest_hash = p_manifest_hash and dst.metadata_version = p_metadata_version
                         and dbms_lob.compare(dst.declaration_json, p_declaration)=0 then dst.verified_yn else 'N' end,
      verified_on = case when dst.manifest_hash = p_manifest_hash and dst.metadata_version = p_metadata_version
                         and dbms_lob.compare(dst.declaration_json, p_declaration)=0 then dst.verified_on else null end,
      plugin_id=p_plugin_id, metadata_version=p_metadata_version, manifest_hash=p_manifest_hash, declaration_json=p_declaration
    when not matched then insert(dataset_id, plugin_id, metadata_version, manifest_hash, declaration_json)
      values(p_dataset_id, p_plugin_id, p_metadata_version, p_manifest_hash, p_declaration);
  end;

  function dataset_available(p_dataset_id in varchar2, p_metadata_version in varchar2, p_manifest_hash in varchar2) return number is
    l_count number;
  begin
    select count(*) into l_count
      from orac_api.relational_query_catalogue_v cat
      join orac_code.plugin_registry_v plugin on plugin.plugin_id=cat.plugin_id
     where cat.dataset_id=p_dataset_id and cat.metadata_version=p_metadata_version
       and cat.manifest_hash=p_manifest_hash and cat.manifest_hash=plugin.manifest_hash
       and cat.verified_yn='Y' and cat.verified_on is not null and cat.evidence_json is not null
       and plugin.enabled='Y' and plugin.removal_id is null and plugin.install_status='success'
       and plugin.readiness_status='success'
       and plugin.database_status in ('deployed','already_deployed');
    return case when l_count=1 then 1 else 0 end;
  end;

  function reviewed_metadata(p_dataset_id in varchar2, p_metadata_version in varchar2,
                             p_manifest_hash in varchar2) return clob is
    l_snapshot clob;
    l_object json_object_t;
    l_keys json_key_list;
    l_element json_element_t;
    l_bytes pls_integer:=0;
    l_offset pls_integer:=1;
    l_chunk varchar2(32767);
    l_valid_json number;
  begin
    if dataset_available(p_dataset_id,p_metadata_version,p_manifest_hash)<>1 then
      raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE');
    end if;
    select json_query(evidence_json,'$.projected_metadata' returning clob error on error)
      into l_snapshot from orac_api.relational_query_catalogue_v
     where dataset_id=p_dataset_id and metadata_version=p_metadata_version and manifest_hash=p_manifest_hash;
    select case when l_snapshot is json strict with unique keys then 1 else 0 end
      into l_valid_json from dual;
    if l_snapshot is null or dbms_lob.getlength(l_snapshot)>131072 or l_valid_json<>1 then
      raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE');
    end if;
    while l_offset<=dbms_lob.getlength(l_snapshot) loop
      l_chunk:=dbms_lob.substr(l_snapshot,8191,l_offset);
      l_bytes:=l_bytes+lengthb(l_chunk);
      if l_bytes>131072 then raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE'); end if;
      l_offset:=l_offset+length(l_chunk);
    end loop;
    l_object:=json_object_t.parse(l_snapshot);
    l_keys:=l_object.get_keys;
    if l_keys.count<>8 then raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE'); end if;
    for idx in 1..l_keys.count loop
      if l_keys(idx) not in ('format','dataset_id','metadata_version','manifest_hash','review_id','views','keys','relationships') then
        raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE');
      end if;
    end loop;
    if nvl(l_object.get_number('format'),0)<>1
       or nvl(l_object.get_string('dataset_id'),chr(0))<>p_dataset_id
       or nvl(l_object.get_string('metadata_version'),chr(0))<>p_metadata_version
       or nvl(l_object.get_string('manifest_hash'),chr(0))<>p_manifest_hash
       or l_object.get_string('review_id') is null
       or length(l_object.get_string('review_id'))>128
       or not l_object.has('views') or not l_object.has('keys') or not l_object.has('relationships') then
      raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE');
    end if;
    l_element:=l_object.get('views');
    if not l_element.is_object then raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE'); end if;
    l_element:=l_object.get('keys');
    if not l_element.is_array then raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE'); end if;
    l_element:=l_object.get('relationships');
    if not l_element.is_array then raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE'); end if;
    return l_snapshot;
  exception when others then
    raise_application_error(-20825,'QUERY_REVIEW_UNAVAILABLE');
  end;

  function request_available(p_request_id in number) return boolean is
    p_request orac_api.relational_query_requests_v%rowtype;
    l_plugin varchar2(128 char);
    l_count number;
  begin
    select * into p_request from orac_api.relational_query_requests_v where request_id=p_request_id;
    select plugin_id into l_plugin from orac_api.relational_query_catalogue_v
     where dataset_id=p_request.dataset_id;
    if dataset_available(p_request.dataset_id, p_request.metadata_version, p_request.manifest_hash) <> 1
       or orac_code.plugin_apex_app_auth_api.plugin_is_available(l_plugin, p_request.application_id) <> 1
    then return false; end if;
    select count(*) into l_count from apex_workspace_sessions
     where apex_session_id=to_number(p_request.apex_session_id)
       and upper(user_name)=upper(p_request.username) and workspace_name='ORAC'
       and session_idle_timeout_on > sysdate and session_life_timeout_on > sysdate;
    if l_count<>1 then return false; end if;
    -- Reapply the installed application's existing role declarations, rather
    -- than inventing a query entitlement or applying app roles to chat.
    for role_rec in (
      select jt.role_name from orac_api.plugin_apex_apps_v app,
        json_table(app.required_roles,'$[*]' columns(role_name varchar2(128) path '$')) jt
       where app.plugin_id=l_plugin and app.installed_app_id=p_request.application_id
    ) loop
      if orac_code.plugin_apex_app_auth_api.has_required_role(role_rec.role_name,p_request.username)<>1
      then return false; end if;
    end loop;
    return true;
  exception when others then return false;
  end;

  procedure claim_next(p_worker in varchar2, p_request_id out number, p_lease out varchar2,
                       p_username out varchar2, p_dataset out varchar2, p_question out varchar2) is
    cursor requests is select * from orac_api.relational_query_requests_v
      where application_id>0 and expires_on>systimestamp and (status_code='QUEUED' or
        (status_code='PROCESSING' and lease_expires_on<systimestamp))
      order by created_on for update skip locked;
  begin
    p_request_id:=null;
    if p_worker is null or length(p_worker)>255 then raise_application_error(-20821,'QUERY_WORKER_INVALID'); end if;
    for rec in requests loop
      if not request_available(rec.request_id) then
        update orac_api.relational_query_requests_v set status_code='FAILED',failure_code='QUERY_UNAVAILABLE',result_json=null
         where request_id=rec.request_id;
        continue;
      end if;
      p_request_id:=rec.request_id; p_lease:=rawtohex(sys_guid());
      p_username:=rec.username; p_dataset:=rec.dataset_id; p_question:=rec.question;
      update orac_api.relational_query_requests_v set status_code='PROCESSING',lease_owner=p_worker,
        lease_token=p_lease,lease_expires_on=systimestamp+interval '3' minute
       where request_id=p_request_id;
      exit;
    end loop;
  end;

  procedure complete_query(p_request_id in number, p_worker in varchar2, p_lease in varchar2,
                           p_result in clob, p_failure in varchar2 default null) is
    l_request orac_api.relational_query_requests_v%rowtype;
    l_snapshot clob;
    l_review varchar2(128 char);
    l_result_review varchar2(128 char);
  begin
    select * into l_request from orac_api.relational_query_requests_v
     where request_id=p_request_id and status_code='PROCESSING' and lease_owner=p_worker
       and lease_token=p_lease and lease_expires_on>systimestamp and expires_on>systimestamp for update;
    if not request_available(l_request.request_id) then
      update orac_api.relational_query_requests_v set status_code='FAILED',failure_code='QUERY_UNAVAILABLE',result_json=null,
        lease_owner=null,lease_token=null,lease_expires_on=null where request_id=p_request_id;
      return;
    end if;
    if p_failure is null and (p_result is null or p_result is not json or dbms_lob.getlength(p_result)>1100000)
    then raise_application_error(-20822,'QUERY_RESULT_INVALID'); end if;
    if p_failure is null then
      l_snapshot:=reviewed_metadata(l_request.dataset_id,l_request.metadata_version,l_request.manifest_hash);
      select json_value(l_snapshot,'$.review_id' returning varchar2(128) error on error),
             json_value(p_result,'$.provenance.review_id' returning varchar2(128) error on error)
        into l_review,l_result_review from dual;
      if l_result_review is null or l_review<>l_result_review then
        update orac_api.relational_query_requests_v set status_code='FAILED',failure_code='REVIEW_CHANGED',result_json=null,
          lease_owner=null,lease_token=null,lease_expires_on=null where request_id=p_request_id;
        return;
      end if;
    end if;
    update orac_api.relational_query_requests_v set
      status_code=case when p_failure is null then 'COMPLETED' else 'FAILED' end,
      result_json=case when p_failure is null then p_result else null end,
      failure_code=substr(p_failure,1,100),lease_owner=null,lease_token=null,lease_expires_on=null
     where request_id=p_request_id;
  exception when no_data_found then raise_application_error(-20823,'QUERY_LEASE_INVALID');
  end;

  procedure audit_event(p_event in clob) is
  begin
    if p_event is null or p_event is not json or dbms_lob.getlength(p_event)>8192
    then raise_application_error(-20824,'QUERY_AUDIT_INVALID'); end if;
    insert into orac_api.relational_query_audit_v(event_json) values(p_event);
  end;

  procedure reserve_query(p_username in varchar2, p_dataset in varchar2, p_existing_id in number, p_token out number) is
    l_recent number;
    l_pending number;
    l_active number;
    l_cat orac_api.relational_query_catalogue_v%rowtype;
  begin
    -- Fixed lock order serializes cross-dataset principal reservations.
    for rec in (select dataset_id from orac_api.relational_query_catalogue_v order by dataset_id for update) loop null; end loop;
    select * into l_cat from orac_api.relational_query_catalogue_v where dataset_id=p_dataset;
    if dataset_available(p_dataset,l_cat.metadata_version,l_cat.manifest_hash)<>1
    then raise_application_error(-20811,'QUERY_UNAVAILABLE'); end if;
    select count(*), count(case when expires_on>systimestamp and (status_code='QUEUED' or (status_code='PROCESSING' and lease_expires_on>systimestamp)) then 1 end)
      into l_recent,l_pending from orac_api.relational_query_requests_v
     where lower(username)=lower(p_username) and created_on>systimestamp-interval '1' hour
       and (p_existing_id is null or request_id<>p_existing_id);
    select count(*) into l_active from orac_api.relational_query_requests_v
     where dataset_id=p_dataset and status_code='PROCESSING' and lease_expires_on>systimestamp
       and (p_existing_id is null or request_id<>p_existing_id);
    if l_recent>=30 or l_pending>=2 or l_active>=2
    then raise_application_error(-20813,'QUERY_RATE_LIMITED'); end if;
    if p_existing_id is not null then
      select -request_id into p_token from orac_api.relational_query_requests_v
       where request_id=p_existing_id and username=p_username and dataset_id=p_dataset
         and status_code='PROCESSING' and lease_expires_on>systimestamp and expires_on>systimestamp;
    else
      insert into orac_api.relational_query_requests_v
        (username,application_id,apex_session_id,dataset_id,metadata_version,manifest_hash,question,
         status_code,lease_expires_on)
      values(p_username,0,'chat',p_dataset,l_cat.metadata_version,l_cat.manifest_hash,'[chat]',
             'PROCESSING',systimestamp+interval '3' minute) returning request_id into p_token;
    end if;
  end;

  procedure release_query(p_token in number) is
  begin
    update orac_api.relational_query_requests_v set status_code='COMPLETED',lease_expires_on=null
     where request_id=p_token and application_id=0;
  end;

  procedure purge_expired is
  begin
    delete from orac_api.relational_query_requests_v where expires_on<=systimestamp;
    delete from orac_api.relational_query_audit_v where created_on<=systimestamp-interval '30' day;
  end;
end relational_query_worker_api;
/
--rollback drop package body orac_code.relational_query_worker_api;
