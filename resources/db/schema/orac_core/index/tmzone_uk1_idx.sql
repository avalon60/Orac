-- __author__: clive
-- __date__: 2026-04-27
-- __description__: unique index for canonical timezone name

create unique index orac_core.tmzone_uk1_idx
  on orac_core.timezones
  (
    tz_name asc
  )
;
