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
before update on orac_core.knowledge_document_versions
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
