-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.devices
  add constraint fk_devices_user
  foreign key
  (
    user_id
  )
  references orac.users
  (
    user_id
  )
  on delete cascade
;
