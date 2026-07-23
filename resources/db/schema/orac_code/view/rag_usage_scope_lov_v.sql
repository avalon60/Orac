--liquibase formatted sql

--changeset clive:create_view_orac_code_rag_usage_scope_lov_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: eligible canonical scope LOV for RAG privilege administration
create or replace force view orac_code.rag_usage_scope_lov_v as
select canonical_scope display_value,
       knowledge_scope_id return_value,
       scope_type,
       scope_key,
       project_id,
       plugin_registry_id
  from orac_code.knowledge_scope_registry_v
 where (scope_type = 'PROJECT' and active_yn = 'Y')
    or (scope_type = 'PLUGIN'
        and active_yn = 'Y'
        and install_status = 'success'
        and configuration_status in ('success', 'not_required')
        and dependency_status in ('success', 'not_required')
        and database_status in (
              'deployed', 'already_deployed', 'not_required', 'optional_missing'
            )
        and readiness_status = 'success');
--rollback drop view orac_code.rag_usage_scope_lov_v;
