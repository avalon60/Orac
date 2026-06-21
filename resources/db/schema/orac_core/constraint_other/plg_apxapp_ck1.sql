-- __author__: clive
-- __date__: 2026-06-20
-- __description__: plugin_apex_apps enabled flag validation

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_ck1
  check (enabled in ('Y', 'N'));
