-- __author__: clive
-- __date__: 2026-04-27
-- __description__: enforce active flag values for timezones

alter table orac_core.timezones
  add constraint tmzone_ck1
  check (is_active in ('N', 'Y'))
;
