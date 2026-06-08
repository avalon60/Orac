-- __author__: clive
-- __date__: 2026-06-07
-- __description__: plugin_registry enabled flag validation

alter table orac_core.plugin_registry add constraint plgreg_ck1
  check (enabled in ('Y', 'N'));
