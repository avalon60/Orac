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
     or updating('CONTENT_URI')
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

--changeset clive:create_trigger_orac_core_kn_chnkemb_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.kn_chnkemb_bu
before update on orac_core.knowledge_chunk_embeddings
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
--rollback drop trigger orac_core.kn_chnkemb_bu;
