--liquibase formatted sql

--changeset clive:create_index_orac_core_kn_scope_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_SCOPE_PK';
create unique index orac_core.kn_scope_pk
  on orac_core.knowledge_scopes (knowledge_scope_id);
--rollback drop index orac_core.kn_scope_pk;

--changeset clive:create_index_orac_core_kn_scope_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_SCOPE_UK1_IDX';
create unique index orac_core.kn_scope_uk1_idx
  on orac_core.knowledge_scopes (project_id);
--rollback drop index orac_core.kn_scope_uk1_idx;

--changeset clive:create_index_orac_core_kn_scope_uk2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_SCOPE_UK2_IDX';
create unique index orac_core.kn_scope_uk2_idx
  on orac_core.knowledge_scopes (plugin_registry_id);
--rollback drop index orac_core.kn_scope_uk2_idx;

--changeset clive:create_index_orac_core_rag_useprv_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'RAG_USEPRV_PK';
create unique index orac_core.rag_useprv_pk
  on orac_core.rag_usage_privileges (rag_usage_privilege_id);
--rollback drop index orac_core.rag_useprv_pk;

--changeset clive:create_index_orac_core_rag_useprv_active_uk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'RAG_USEPRV_ACTIVE_UK_IDX';
create unique index orac_core.rag_useprv_active_uk_idx
  on orac_core.rag_usage_privileges (
    case when active_yn = 'Y' then user_id end,
    case when active_yn = 'Y' then knowledge_scope_id end,
    case when active_yn = 'Y' then privilege_code end
  );
--rollback drop index orac_core.rag_useprv_active_uk_idx;

--changeset clive:create_index_orac_core_rag_useprv_scope_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'RAG_USEPRV_SCOPE_IDX';
create index orac_core.rag_useprv_scope_idx
  on orac_core.rag_usage_privileges (knowledge_scope_id, user_id, active_yn);
--rollback drop index orac_core.rag_useprv_scope_idx;

--changeset clive:create_index_orac_core_kn_srcobj_scope_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_SRCOBJ_SCOPE_IDX';
create index orac_core.kn_srcobj_scope_idx
  on orac_core.knowledge_source_objects (knowledge_scope_id);
--rollback drop index orac_core.kn_srcobj_scope_idx;

--changeset clive:create_index_orac_core_plgsvc_registry_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLGSVC_REGISTRY_IDX';
create index orac_core.plgsvc_registry_idx
  on orac_core.plugin_services (plugin_registry_id);
--rollback drop index orac_core.plgsvc_registry_idx;
