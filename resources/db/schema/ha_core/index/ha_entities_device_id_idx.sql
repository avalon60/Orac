-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.ha_entities_device_id_idx
  on orac.ha_entities
  (
    device_id asc
  )
logging
;
