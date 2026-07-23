--liquibase formatted sql

--changeset clive:create_constraint_other_orac_core_kn_scope_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SCOPE_CK1';
alter table orac_core.knowledge_scopes add constraint kn_scope_ck1 check (
  (scope_type = 'PROJECT' and project_id is not null and plugin_registry_id is null)
  or
  (scope_type = 'PLUGIN' and project_id is null and plugin_registry_id is not null)
);
--rollback alter table orac_core.knowledge_scopes drop constraint kn_scope_ck1;

--changeset clive:create_constraint_other_orac_core_rag_useprv_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'RAG_USEPRV_CK1';
alter table orac_core.rag_usage_privileges add constraint rag_useprv_ck1
  check (privilege_code = 'USE');
--rollback alter table orac_core.rag_usage_privileges drop constraint rag_useprv_ck1;

--changeset clive:create_constraint_other_orac_core_rag_useprv_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'RAG_USEPRV_CK2';
alter table orac_core.rag_usage_privileges add constraint rag_useprv_ck2
  check (active_yn in ('Y', 'N'));
--rollback alter table orac_core.rag_usage_privileges drop constraint rag_useprv_ck2;

--changeset clive:create_constraint_other_orac_core_rag_useprv_ck3 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'RAG_USEPRV_CK3';
alter table orac_core.rag_usage_privileges add constraint rag_useprv_ck3 check (
  expires_on is null or expires_on > effective_on
);
--rollback alter table orac_core.rag_usage_privileges drop constraint rag_useprv_ck3;

--changeset clive:create_constraint_other_orac_core_rag_useprv_ck4 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'RAG_USEPRV_CK4';
alter table orac_core.rag_usage_privileges add constraint rag_useprv_ck4 check (
  (active_yn = 'Y' and revoked_on is null and revoked_by is null and revoke_reason_code is null)
  or
  (active_yn = 'N' and revoked_on is not null and revoked_by is not null and revoke_reason_code is not null)
);
--rollback alter table orac_core.rag_usage_privileges drop constraint rag_useprv_ck4;

--changeset clive:create_constraint_other_orac_core_plgsvc_owner_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGSVC_OWNER_CK';
alter table orac_core.plugin_services add constraint plgsvc_owner_ck check (
  (service_owner_type = 'CORE' and plugin_registry_id is null and plugin_id = 'orac_core')
  or
  (service_owner_type = 'PLUGIN' and plugin_registry_id is not null)
);
--rollback alter table orac_core.plugin_services drop constraint plgsvc_owner_ck;

--changeset clive:create_constraint_other_orac_core_users_trim_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'USERS_TRIM_CK';
--precondition-sql-check expectedResult:0 select count(1) from orac_core.users where username <> trim(username);
alter table orac_core.users add constraint users_trim_ck check (username = trim(username));
--rollback alter table orac_core.users drop constraint users_trim_ck;
