-- __author__: clive bostock
-- __date__: 2025-12-28
-- __description__: generated/synchronised by Cline; one object per file

alter table orac.ha_entities
  add constraint ha_entities_options_json
  check (options is json);
