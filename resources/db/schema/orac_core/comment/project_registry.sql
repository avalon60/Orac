--liquibase formatted sql

--changeset clive:comment_orac_core_project_registry context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.project_registry is
  'Stores core-owned project codes available to Orac routing and ingestion configuration.';

comment on column orac_core.project_registry.project_id is
  'Surrogate identifier for a registered project.';

comment on column orac_core.project_registry.project_code is
  'Stable uppercase project code used by routed ingestion target keys.';

comment on column orac_core.project_registry.display_name is
  'Human-readable project name shown in administration surfaces.';

comment on column orac_core.project_registry.description is
  'Optional project description for administration surfaces.';

comment on column orac_core.project_registry.active_yn is
  'Y when the project can be selected for new routing configuration.';

comment on column orac_core.project_registry.row_version is
  'Optimistic locking version maintained on update.';
