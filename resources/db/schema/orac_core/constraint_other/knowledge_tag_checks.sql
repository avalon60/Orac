--liquibase formatted sql

--changeset clive:create_knowledge_tag_checks context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name in ('KN_TAG_CODE_CK','KN_TAG_FLAGS_CK','KN_DOCVTAG_ORDER_CK');
alter table orac_core.knowledge_tags add constraint kn_tag_code_ck check (regexp_like(tag_code, '^[a-z][a-z0-9_]{1,99}$'));
alter table orac_core.knowledge_tags add constraint kn_tag_flags_ck check (active_yn in ('Y','N') and system_yn in ('Y','N'));
alter table orac_core.knowledge_document_version_tags add constraint kn_docvtag_order_ck check (tag_order between 1 and 10);
--rollback alter table orac_core.knowledge_document_version_tags drop constraint kn_docvtag_order_ck; alter table orac_core.knowledge_tags drop constraint kn_tag_flags_ck; alter table orac_core.knowledge_tags drop constraint kn_tag_code_ck;
