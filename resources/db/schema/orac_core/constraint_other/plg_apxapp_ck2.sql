-- __author__: clive
-- __date__: 2026-06-20
-- __description__: plugin_apex_apps install status validation

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_ck2
  check (install_status in ('metadata_only', 'pending', 'installed', 'failed', 'skipped'));
