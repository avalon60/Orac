-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.ha_entities
  add constraint ha_entities_devices_fk
  foreign key
  (
    device_id
  )
  references orac.ha_devices
  (
    device_id
  )
  not deferrable
;
