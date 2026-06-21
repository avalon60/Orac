-- __author__: clive
-- __date__: 2026-06-20
-- __description__: one current APEX app registry row per plugin alias

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_uk1
  unique (plugin_id, app_alias) using index orac_core.plg_apxapp_uk1_idx;
