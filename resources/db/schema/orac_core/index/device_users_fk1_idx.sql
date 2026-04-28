-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac_core.device_users_fk1_idx
  on orac_core.devices
  (
    user_id asc
  )
;
