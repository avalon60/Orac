-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.ha_areas
  add constraint ha_areas_pk
  primary key (area_id)
  using index orac.ha_areas_pk_idx
;
