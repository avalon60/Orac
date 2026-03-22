-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.devices_uid_idx
  on orac.devices
  (
    user_id asc
  )
;
