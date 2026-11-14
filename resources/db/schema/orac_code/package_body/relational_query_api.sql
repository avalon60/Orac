--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_code_package_body_relational_query_api context:core labels:core,relational_query stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package body orac_code.relational_query_api as
  procedure identity(p_user out varchar2, p_app out number, p_session out varchar2) is
    l_app varchar2(30 char);
  begin
    p_user := nullif(trim(sys_context('APEX$SESSION', 'APP_USER')), '');
    l_app := sys_context('APEX$SESSION', 'APP_ID');
    p_session := sys_context('APEX$SESSION', 'APP_SESSION');
    if p_user is null or upper(p_user) in ('NOBODY', 'APEX_PUBLIC_USER', 'SYSTEM')
       or length(p_user) > 128 or not regexp_like(l_app, '^[0-9]+$')
       or p_session is null or not apex_authentication.is_authenticated
    then
      raise_application_error(-20810, 'QUERY_SESSION_REQUIRED');
    end if;
    p_app := to_number(l_app);
  end;

  procedure available(p_dataset in varchar2, p_app in number,
                      p_version out varchar2, p_hash out varchar2) is
    l_plugin varchar2(128 char);
  begin
    select cat.plugin_id, cat.metadata_version, cat.manifest_hash
      into l_plugin, p_version, p_hash
      from orac_api.relational_query_catalogue_v cat
      join orac_code.plugin_registry_v plugin on plugin.plugin_id = cat.plugin_id
     where cat.dataset_id = p_dataset and cat.verified_yn = 'Y'
       and cat.verified_on is not null and cat.evidence_json is not null
       and cat.manifest_hash = plugin.manifest_hash;
    if orac_code.plugin_apex_app_auth_api.plugin_is_available(l_plugin, p_app) <> 1

    then
      raise no_data_found;
    end if;
    for role_rec in (
      select jt.role_name from orac_api.plugin_apex_apps_v app,
        json_table(app.required_roles,'$[*]' columns(role_name varchar2(128) path '$')) jt
       where app.plugin_id=l_plugin and app.installed_app_id=p_app
    ) loop
      if orac_code.plugin_apex_app_auth_api.has_required_role(role_rec.role_name)<>1
      then raise no_data_found; end if;
    end loop;
  exception
    when no_data_found or too_many_rows then
      raise_application_error(-20811, 'QUERY_UNAVAILABLE');
  end;

  procedure submit_query(p_dataset_id in varchar2, p_question in varchar2, p_request_id out number) is
    l_user varchar2(128 char);
    l_app number;
    l_session varchar2(128 char);
    l_version varchar2(128 char);
    l_hash varchar2(64 char);
    l_recent number;
    l_pending number;
  begin
    identity(l_user, l_app, l_session);
    available(p_dataset_id, l_app, l_version, l_hash);
    if trim(p_question) is null or length(p_question) > 2048
    then
      raise_application_error(-20812, 'QUERY_QUESTION_INVALID');
    end if;
    -- Serialize principal reservations across APEX sessions to close races.
    for rec in (select dataset_id from orac_api.relational_query_catalogue_v
                order by dataset_id for update) loop null; end loop;
    select count(*), count(case when expires_on>systimestamp and (status_code='QUEUED' or (status_code='PROCESSING' and lease_expires_on>systimestamp)) then 1 end)
      into l_recent, l_pending from orac_api.relational_query_requests_v
     where lower(username) = lower(l_user) and created_on > systimestamp - interval '1' hour;
    if l_recent >= 30 or l_pending >= 2
    then
      raise_application_error(-20813, 'QUERY_RATE_LIMITED');
    end if;
    insert into orac_api.relational_query_requests_v
      (username, application_id, apex_session_id, dataset_id, metadata_version, manifest_hash, question)
    values (l_user, l_app, l_session, p_dataset_id, l_version, l_hash, trim(p_question))
    returning request_id into p_request_id;
  end;

  procedure read_query(p_request_id in number, p_status out varchar2, p_result out clob) is
    l_user varchar2(128 char);
    l_app number;
    l_session varchar2(128 char);
    l_version varchar2(128 char);
    l_hash varchar2(64 char);
    l_request orac_api.relational_query_requests_v%rowtype;
    l_snapshot clob;
    l_review varchar2(128 char);
    l_result_review varchar2(128 char);
  begin
    identity(l_user, l_app, l_session);
    select * into l_request from orac_api.relational_query_requests_v
     where request_id = p_request_id and username = l_user
       and application_id = l_app and apex_session_id = l_session;
    available(l_request.dataset_id, l_app, l_version, l_hash);
    if l_request.metadata_version <> l_version or l_request.manifest_hash <> l_hash
    then
      raise_application_error(-20811, 'QUERY_UNAVAILABLE');
    end if;
    p_status := case when l_request.expires_on <= systimestamp then 'EXPIRED' else l_request.status_code end;
    p_result := case when p_status = 'COMPLETED' then l_request.result_json else null end;
    if p_status='COMPLETED' then
      l_snapshot:=orac_code.relational_query_worker_api.reviewed_metadata(l_request.dataset_id,l_version,l_hash);
      select json_value(l_snapshot,'$.review_id' returning varchar2(128) error on error),
             json_value(p_result,'$.provenance.review_id' returning varchar2(128) error on error)
        into l_review,l_result_review from dual;
      if l_result_review is null or l_review<>l_result_review then
        raise_application_error(-20811,'QUERY_UNAVAILABLE');
      end if;
    end if;
  exception
    when no_data_found then
      raise_application_error(-20814, 'QUERY_REQUEST_UNAVAILABLE');
  end;
end relational_query_api;
/
--rollback drop package body orac_code.relational_query_api;
