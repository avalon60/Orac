-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.devices
  add constraint devices_cc1
  check (is_active in ('N', 'Y'))
;
