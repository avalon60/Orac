-- __author__: clive
-- __date__: 2026-04-27
-- __description__: unique constraint for canonical timezone name

alter table orac_core.timezones
  add constraint tmzone_uk1
  unique (tz_name)
;
