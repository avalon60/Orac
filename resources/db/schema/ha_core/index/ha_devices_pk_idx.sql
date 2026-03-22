-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac.ha_devices_pk_idx
  on orac.ha_devices
  (
    device_id asc
  )
logging
;
