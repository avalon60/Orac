-- __author__: clive
-- __date__: 2026-06-07
-- __description__: primary key for plugin_registry

alter table orac_core.plugin_registry add constraint plgreg_pk
  primary key (plugin_registry_id) using index orac_core.plgreg_pk;
