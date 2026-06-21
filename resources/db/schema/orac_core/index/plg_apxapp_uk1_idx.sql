-- __author__: clive
-- __date__: 2026-06-20
-- __description__: unique plugin APEX app alias index

create unique index orac_core.plg_apxapp_uk1_idx
  on orac_core.plugin_apex_apps(plugin_id, app_alias);
