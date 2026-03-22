-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.ha_devices
  add constraint ha_devices_areas_fk
  foreign key
  (
    area_id
  )
  references orac.ha_areas
  (
    area_id
  )
  not deferrable
;
