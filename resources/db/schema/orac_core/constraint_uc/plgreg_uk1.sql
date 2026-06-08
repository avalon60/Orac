-- __author__: clive
-- __date__: 2026-06-07
-- __description__: one current registry row per plugin

alter table orac_core.plugin_registry add constraint plgreg_uk1
  unique (plugin_id) using index orac_core.plgreg_uk1_idx;
