-- __author__: clive
-- __date__: 2026-06-20
-- __description__: primary key for plugin_apex_apps

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_pk
  primary key (plugin_apex_app_id) using index orac_core.plg_apxapp_pk;
