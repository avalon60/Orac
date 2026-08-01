--liquibase formatted sql
-- Author: clive
-- Date: 26-Jul-2026
-- Description: Seeds the canonical Orac documentation project and knowledge scope.

--changeset clive:seed_orac_core_project_registry_orac_core context:core labels:core stripComments:false
-- __author__: clive
-- __date__: 2026-07-26
-- __description__: seed the canonical Orac documentation project without inferring projects from adapter configuration

merge into orac_core.project_registry dst
using (
  select 'ORAC_CORE' project_code,
         'Orac Core' display_name,
         'Canonical scope for Orac-wide architecture, configuration, guardrail, and operator documentation.' description
    from dual
) src
on (dst.project_code = src.project_code)
when matched then
  update set
    dst.display_name = src.display_name,
    dst.description  = src.description,
    dst.active_yn    = 'Y'
when not matched then
  insert (
    project_code,
    display_name,
    description,
    active_yn
  ) values (
    src.project_code,
    src.display_name,
    src.description,
    'Y'
  );

insert into orac_core.knowledge_scopes (
  scope_type,
  project_id
)
select 'PROJECT',
       project.project_id
  from orac_core.project_registry project
 where project.project_code = 'ORAC_CORE'
   and not exists (
         select 1
           from orac_core.knowledge_scopes scope
          where scope.project_id = project.project_id
       );

--rollback select 1 from dual;
