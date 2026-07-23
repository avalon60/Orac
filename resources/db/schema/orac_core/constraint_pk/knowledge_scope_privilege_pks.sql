--liquibase formatted sql

--changeset clive:create_constraint_pk_orac_core_kn_scope_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SCOPE_PK';
alter table orac_core.knowledge_scopes add constraint kn_scope_pk
  primary key (knowledge_scope_id)
  using index orac_core.kn_scope_pk;
--rollback alter table orac_core.knowledge_scopes drop constraint kn_scope_pk;

--changeset clive:create_constraint_pk_orac_core_rag_useprv_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'RAG_USEPRV_PK';
alter table orac_core.rag_usage_privileges add constraint rag_useprv_pk
  primary key (rag_usage_privilege_id)
  using index orac_core.rag_useprv_pk;
--rollback alter table orac_core.rag_usage_privileges drop constraint rag_useprv_pk;
