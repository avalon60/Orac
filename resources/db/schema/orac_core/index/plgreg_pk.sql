-- __author__: clive
-- __date__: 2026-06-07
-- __description__: primary key index for plugin_registry

create unique index orac_core.plgreg_pk
  on orac_core.plugin_registry(plugin_registry_id);
