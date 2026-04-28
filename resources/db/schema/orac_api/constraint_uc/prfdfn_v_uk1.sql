-- __author__: clive
-- __date__: 2026-04-27
-- __description__: unique key metadata for the published preference definitions view

alter view orac_api.preference_definitions_v
  add constraint prfdfn_v_uk1
  unique (pref_key)
  rely disable novalidate
;
