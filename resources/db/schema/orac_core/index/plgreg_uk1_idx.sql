-- __author__: clive
-- __date__: 2026-06-07
-- __description__: unique plugin identifier index for plugin_registry

create unique index orac_core.plgreg_uk1_idx
  on orac_core.plugin_registry(plugin_id);
