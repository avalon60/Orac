-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.ha_devices
  add constraint ha_devices_config_entries_json
  check (config_entries is json)
;
