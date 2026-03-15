-- __author__: clive bostock
-- __date__: 2025-12-28
-- __description__: generated/synchronised by Cline; one object per file

alter table orac.ha_devices
  add constraint ha_devices_areas_fk
  foreign key (area_id)
  references orac.ha_areas (area_id);
