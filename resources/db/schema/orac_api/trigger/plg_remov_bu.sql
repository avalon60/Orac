--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Maintains immutable attribution and audit fields for plugin_removals.

--changeset clive:create_trigger_orac_api_plg_remov_bu context:core labels:core stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace trigger orac_api.plg_remov_bu
before update on orac_core.plugin_removals
for each row
declare
  l_old_json clob;
  l_new_json clob;
  l_old_object json_object_t;
  l_new_object json_object_t;
  l_keys json_key_list;
  l_old_value json_element_t;
  l_new_value json_element_t;
  l_equal number;
begin
  if updating('CHECKPOINTS')
  then
    select json_serialize(:old.checkpoints returning clob),
           json_serialize(:new.checkpoints returning clob)
      into l_old_json, l_new_json from dual;
    if l_new_json is null or dbms_lob.getlength(l_new_json) > 65536
    then
      raise_application_error(-20070, 'Removal checkpoints must be bounded.');
    end if;
    if l_old_json is null
    then
      l_old_object := json_object_t();
    else
      l_old_object := json_object_t.parse(l_old_json);
    end if;
    l_new_object := json_object_t.parse(l_new_json);
    l_keys := l_old_object.get_keys;
    for i in 1 .. l_keys.count
    loop
      if not l_new_object.has(l_keys(i))
      then
        raise_application_error(-20070, 'Verified cleanup checkpoints cannot be removed.');
      end if;
      l_old_value := l_old_object.get(l_keys(i));
      l_new_value := l_new_object.get(l_keys(i));
      l_old_json := l_old_value.to_clob();
      l_new_json := l_new_value.to_clob();
      select case when json_equal(l_old_json, l_new_json) then 1 else 0 end
        into l_equal from dual;
      if l_equal <> 1
      then
        raise_application_error(-20070, 'Verified cleanup checkpoints cannot change.');
      end if;
    end loop;
  end if;
  if updating('RESOURCE_INVENTORY')
  then
    raise_application_error(-20070, 'Authorized removal inventory cannot change on retry.');
  end if;
  if :old.completed_on is not null
     or :new.removal_id <> :old.removal_id
     or :new.knowledge_scope_id <> :old.knowledge_scope_id
     or :new.schema_disposition <> :old.schema_disposition
     or :new.manifest_hash <> :old.manifest_hash
     or :new.plugin_version <> :old.plugin_version
     or :new.confirmed_by <> :old.confirmed_by
     or (:old.external_complete_yn = 'Y' and :new.external_complete_yn <> 'Y')
     or (:old.files_complete_yn = 'Y' and :new.files_complete_yn <> 'Y')
  then
    raise_application_error(-20070, 'Removal authorization and completed checkpoints are immutable.');
  end if;
  if :new.plugin_id <> :old.plugin_id or :new.plugin_registry_id <> :old.plugin_registry_id
     or :new.database_identity <> :old.database_identity
  then
    raise_application_error(-20070, 'Plugin lifecycle target attribution is immutable.');
  end if;
  :new.created_on := :old.created_on;
  :new.created_by := :old.created_by;
  :new.updated_on := systimestamp;
  :new.updated_by := sys_context('userenv', 'session_user');
  :new.row_version := :old.row_version + 1;
end;
/
--rollback drop trigger orac_api.plg_remov_bu;
