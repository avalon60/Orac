-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.ha_devices_area_id_idx
  on orac.ha_devices
  (
    area_id asc
  )
logging
;
