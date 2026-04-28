-- __author__: clive
-- __date__: 2026-04-27
-- __description__: primary key constraint for timezones

alter table orac_core.timezones
  add constraint tmzone_pk
  primary key (timezone_id)
;
