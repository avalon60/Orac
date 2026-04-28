-- __author__: clive
-- __date__: 2026-04-27
-- __description__: primary key index for timezones

create unique index orac_core.tmzone_pk
  on orac_core.timezones
  (
    timezone_id asc
  )
;
