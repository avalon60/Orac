--liquibase formatted sql

--changeset clive:create_trigger_orac_core_kn_srcobj_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_srcobj_bu
before update on orac_core.knowledge_source_objects
for each row
begin
  -- Recompile after canonical scope normalization changes the source table shape.
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
--rollback drop trigger orac_core.kn_srcobj_bu;

--changeset clive:create_trigger_orac_core_kn_doc_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_doc_bu
before update on orac_core.knowledge_documents
for each row
begin
  -- Recompile after canonical scope normalization changes the document table shape.
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
--rollback drop trigger orac_core.kn_doc_bu;

--changeset clive:create_trigger_orac_core_kn_docver_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_docver_bu
before update or delete on orac_core.knowledge_document_versions
for each row
declare
  function called_from_migration_api return boolean
  is
  begin
    for l_depth in 1 .. utl_call_stack.dynamic_depth
    loop
      if utl_call_stack.owner(l_depth) = 'ORAC_CODE'
         and instr(
               utl_call_stack.concatenate_subprogram(
                 utl_call_stack.subprogram(l_depth)
               ),
               'KNOWLEDGE_MIGRATION_API'
             ) > 0
      then
        return true;
      end if;
    end loop;
    return false;
  end called_from_migration_api;

  function is_approved_locator_migration return boolean
  is
    l_legacy_uri varchar2(1000);
  begin
    l_legacy_uri := 'sha256/' || substr(:old.content_sha256, 1, 2) || '/'
                    || substr(:old.content_sha256, 3, 2) || '/'
                    || :old.content_sha256;
    return called_from_migration_api
       and :old.content_uri = l_legacy_uri
       and :new.content_uri = 'sha256:' || :old.content_sha256;
  end is_approved_locator_migration;
begin
  if deleting
  then
    raise_application_error(
      -20520,
      'Knowledge document versions are immutable and cannot be deleted.'
    );
  end if;
  if updating('DOCUMENT_VERSION_ID')
     or updating('DOCUMENT_ID')
     or updating('SOURCE_OBJECT_ID')
     or updating('CONTENT_SHA256')
     or updating('MIME_TYPE')
     or updating('ORIGINAL_FILENAME')
     or updating('BYTE_SIZE')
     or updating('SOURCE_MODIFIED_ON')
     or updating('SOURCE_FORMAT_CODE')
     or updating('CREATED_BY')
     or updating('CREATED_ON')
  then
    raise_application_error(
      -20521,
      'Knowledge document-version identity and provenance are immutable.'
    );
  end if;
  if updating('CONTENT_URI') and not is_approved_locator_migration
  then
    raise_application_error(
      -20521,
      'Knowledge document-version identity and provenance are immutable.'
    );
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
--rollback drop trigger orac_core.kn_docver_bu;

--changeset clive:create_trigger_orac_core_kn_ingreq_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_ingreq_bu
before update on orac_core.knowledge_ingestion_requests
for each row
begin
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
--rollback drop trigger orac_core.kn_ingreq_bu;

--changeset clive:create_trigger_orac_core_kn_ext_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_ext_bu
before update on orac_core.knowledge_extractions
for each row
begin
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
--rollback drop trigger orac_core.kn_ext_bu;

--changeset clive:create_trigger_orac_core_kn_chset_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_chset_bu
before update on orac_core.knowledge_chunk_sets
for each row
begin
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
--rollback drop trigger orac_core.kn_chset_bu;

--changeset clive:create_trigger_orac_core_kn_chnk_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_chnk_bu
before update on orac_core.knowledge_chunks
for each row
begin
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
--rollback drop trigger orac_core.kn_chnk_bu;

--changeset clive:create_trigger_orac_core_kn_embmod_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_embmod_bu
before update on orac_core.knowledge_embedding_models
for each row
begin
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
--rollback drop trigger orac_core.kn_embmod_bu;
