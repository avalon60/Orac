--liquibase formatted sql

--changeset clive:drop_box_trigger_drp_job_biu context:plugin,prod labels:plugin,drop_box stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_dropbox.drp_job_biu
before insert or update on orac_dropbox.drop_job
for each row
declare
  l_actor varchar2(128 char) := coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     );
begin
  if inserting
  then
    :new.created_by := coalesce(:new.created_by, l_actor);
    :new.created_on := coalesce(:new.created_on, systimestamp);
    :new.updated_by := coalesce(:new.updated_by, :new.created_by, l_actor);
    :new.updated_on := coalesce(:new.updated_on, :new.created_on, systimestamp);
    :new.row_version := coalesce(:new.row_version, 1);
  else
    if :new.target_knowledge_scope_id <> :old.target_knowledge_scope_id
       or :new.target_knowledge_scope_id is null
       or :new.producer_knowledge_scope_id <> :old.producer_knowledge_scope_id
       or :new.producer_knowledge_scope_id is null
       or :new.effective_scope_type <> :old.effective_scope_type
       or :new.effective_scope_key <> :old.effective_scope_key
    then
      raise_application_error(-20409, 'Queued knowledge target is immutable.');
    end if;
    :new.created_by := :old.created_by;
    :new.created_on := :old.created_on;
    :new.updated_by := l_actor;
    :new.updated_on := systimestamp;
    :new.row_version := nvl(:old.row_version, 1) + 1;
  end if;
end;
/

--rollback drop trigger orac_dropbox.drp_job_biu;
