comment on table orac_core.plugin_apex_apps is
  'Stores plugin-supplied APEX application installation and launch metadata.';

comment on column orac_core.plugin_apex_apps.app_alias is
  'Stable logical APEX application alias declared by the plugin manifest.';

comment on column orac_core.plugin_apex_apps.installed_app_id is
  'APEX application id resolved after a successful import.';

comment on column orac_core.plugin_apex_apps.install_status is
  'Current plugin APEX app lifecycle status.';

comment on column orac_core.plugin_apex_apps.install_log is
  'Captured importer output for diagnostics.';

comment on column orac_core.plugin_apex_apps.enabled is
  'Y when the app should be visible to plugin app listing queries.';
