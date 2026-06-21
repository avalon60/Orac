-- __author__: clive
-- __date__: 2026-06-20
-- __description__: installed APEX application lookup index

create index orac_core.plg_apxapp_idx1
  on orac_core.plugin_apex_apps(workspace, installed_app_id);
