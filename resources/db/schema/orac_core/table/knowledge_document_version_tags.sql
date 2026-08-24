--liquibase formatted sql

--changeset clive:create_table_orac_core_knowledge_document_version_tags context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'KNOWLEDGE_DOCUMENT_VERSION_TAGS';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: authoritative document-version classification assignments

create table orac_core.knowledge_document_version_tags
(
  document_version_id       number not null,
  doc_class_domain_code     varchar2(100 char)
                              default on null 'DOC_CLASS' not null,
  doc_class_ref_value_code  varchar2(100 char) not null,
  tag_order                 number not null,
  created_by                varchar2(128 char) default on null coalesce(
                              sys_context('apex$session', 'app_user'),
                              sys_context('userenv', 'proxy_user'),
                              sys_context('userenv', 'session_user'),
                              user
                            ) not null,
  created_on                timestamp with time zone
                              default on null systimestamp not null
);

--rollback drop table orac_core.knowledge_document_version_tags purge;
