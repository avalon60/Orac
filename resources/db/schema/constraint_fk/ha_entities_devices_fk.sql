-- __author__: clive bostock
-- __date__: 2025-12-28
-- __description__: generated/synchronised by Cline; one object per file

alter table orac.ha_entities
  add constraint ha_entities_devices_fk
  foreign key (device_id)
  references orac.ha_devices (device_id);
