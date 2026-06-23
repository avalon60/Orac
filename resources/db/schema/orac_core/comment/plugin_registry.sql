--liquibase formatted sql

--changeset clive:comment_orac_core_comment_plugin_registry context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.plugin_registry is
  'Stores current Orac plugin installation, readiness and activation state.';

comment on column orac_core.plugin_registry.plugin_id is
  'Stable plugin identifier declared by the plugin manifest.';

comment on column orac_core.plugin_registry.installed_path is
  'Active versioned plugin installation directory.';

comment on column orac_core.plugin_registry.enabled is
  'Y only when all required installation and readiness gates succeeded.';

comment on column orac_core.plugin_registry.row_version is
  'Optimistic locking version maintained on update.';
