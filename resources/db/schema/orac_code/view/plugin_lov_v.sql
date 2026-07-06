--liquibase formatted sql

--changeset clive:create_view_orac_code_view_plugin_lov_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: narrow installed-plugin list of values for APEX configuration surfaces

create or replace force view orac_code.plugin_lov_v as
select plugin_id,
       coalesce(plugin_name, plugin_id) display_label,
       plugin_version,
       install_status,
       readiness_status,
       enabled
  from orac_code.plugin_registry_v
 where enabled = 'Y'
   and install_status = 'success'
   and configuration_status in ('success', 'not_required')
   and dependency_status in ('success', 'not_required')
   and database_status in (
         'deployed',
         'already_deployed',
         'not_required',
         'optional_missing'
       )
   and readiness_status = 'success';

--rollback drop view orac_code.plugin_lov_v;
