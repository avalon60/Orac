--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Relates resolved retrieval events to principals and scopes.

--changeset clive:create_constraint_fk_orac_core_kn_retev_users_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_RETEV_USERS_FK1';
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_users_fk1
  foreign key (user_id) references orac_core.users (user_id);
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_users_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_retev_kn_scope_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_RETEV_KN_SCOPE_FK1';
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_kn_scope_fk1
  foreign key (knowledge_scope_id)
  references orac_core.knowledge_scopes (knowledge_scope_id);
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_kn_scope_fk1;
