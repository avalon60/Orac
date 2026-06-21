-- __author__: clive
-- __date__: 2026-06-20
-- __description__: primary key index for plugin_apex_apps

create unique index orac_core.plg_apxapp_pk
  on orac_core.plugin_apex_apps(plugin_apex_app_id);
