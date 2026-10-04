--liquibase formatted sql

--changeset clive:create_trigger_orac_core_kn_scope_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: preserve canonical scope ownership and maintain audit metadata
create or replace trigger orac_core.kn_scope_bu
before update on orac_core.knowledge_scopes
for each row
begin
  if :new.scope_type <> :old.scope_type
     or nvl(:new.project_id, -1) <> nvl(:old.project_id, -1)
     or nvl(:new.plugin_id, chr(0)) <> nvl(:old.plugin_id, chr(0))
  then
    raise_application_error(-20050, 'Canonical knowledge scope ownership cannot be changed.');
  end if;

  if :old.retired_on is not null
     and (:new.retired_on is null or :new.retired_on <> :old.retired_on)
  then
    raise_application_error(-20050, 'Retired knowledge scopes cannot be revived.');
  end if;

  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version, 1) + 1;
end;
/
--rollback drop trigger orac_core.kn_scope_bu;

--changeset clive:create_trigger_orac_core_rag_useprv_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.rag_useprv_bu
before update on orac_core.rag_usage_privileges
for each row
begin
  if :new.user_id <> :old.user_id
     or :new.knowledge_scope_id <> :old.knowledge_scope_id
     or :new.privilege_code <> :old.privilege_code
     or :new.effective_on <> :old.effective_on
     or nvl(:new.expires_on, to_timestamp_tz('1900-01-01 UTC', 'YYYY-MM-DD TZR')) <>
        nvl(:old.expires_on, to_timestamp_tz('1900-01-01 UTC', 'YYYY-MM-DD TZR'))
  then
    raise_application_error(-20051, 'Historical RAG usage privilege identity cannot be changed.');
  end if;

  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version, 1) + 1;
end;
/
--rollback drop trigger orac_core.rag_useprv_bu;

--changeset clive:create_trigger_orac_core_prjreg_bd context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.prjreg_bd
before delete on orac_core.project_registry
begin
  raise_application_error(-20052, 'Registered projects cannot be physically deleted; deactivate the project instead.');
end;
/
--rollback drop trigger orac_core.prjreg_bd;

--changeset clive:create_trigger_orac_core_plgreg_bd context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.plgreg_bd
before delete on orac_core.plugin_registry
for each row
declare
  l_completed number;
begin
  select count(*) into l_completed
    from orac_core.plugin_removals removal
    join orac_core.knowledge_scopes scope on scope.knowledge_scope_id = removal.knowledge_scope_id
   where removal.plugin_registry_id = :old.plugin_registry_id
     and removal.plugin_id = :old.plugin_id
     and removal.knowledge_scope_id = :old.knowledge_scope_id
     and removal.completed_on is not null
     and removal.external_complete_yn = 'Y' and removal.files_complete_yn = 'Y'
     and scope.retired_on is not null;
  if :old.enabled <> 'N' or l_completed <> 1
  then
    raise_application_error(-20053, 'Plugin deletion requires completed, fenced removal.');
  end if;
end;
/
--rollback drop trigger orac_core.plgreg_bd;

--changeset clive:create_trigger_orac_core_kn_scope_bd context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_scope_bd
before delete on orac_core.knowledge_scopes
begin
  raise_application_error(-20054, 'Canonical knowledge scopes cannot be physically deleted.');
end;
/
--rollback drop trigger orac_core.kn_scope_bd;

--changeset clive:create_trigger_orac_core_users_bi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.users_bi
before insert on orac_core.users
for each row
begin
  if lower(:new.username) = 'system'
  then
    :new.username := 'system';
    :new.is_active := 'N';
  end if;

  if :new.username <> trim(:new.username)
  then
    raise_application_error(-20058, 'Username must not contain surrounding whitespace.');
  end if;
end;
/
--rollback drop trigger orac_core.users_bi;
