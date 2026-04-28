comment on table orac_core.timezones is
  'Curated canonical timezone catalogue used for user-facing LOVs and validation.'
;

comment on column orac_core.timezones.timezone_id is
  'Primary key for the timezone row.'
;

comment on column orac_core.timezones.tz_name is
  'Canonical timezone region name stored in preferences, for example Europe/London.'
;

comment on column orac_core.timezones.display_label is
  'User-friendly display label shown in LOVs and preference editors.'
;

comment on column orac_core.timezones.region_group is
  'High-level grouping used to organise timezone LOVs, for example Europe or North America.'
;

comment on column orac_core.timezones.display_sequence is
  'Display ordering used within a region group.'
;

comment on column orac_core.timezones.is_active is
  'Indicates whether the timezone may be selected by users.'
;

comment on column orac_core.timezones.created_on is
  'Timestamp when the row was created.'
;

comment on column orac_core.timezones.created_by is
  'User or process that created the row.'
;

comment on column orac_core.timezones.updated_on is
  'Timestamp when the row was last updated.'
;

comment on column orac_core.timezones.updated_by is
  'User or process that last updated the row.'
;

comment on column orac_core.timezones.row_version is
  'Row version number used for optimistic locking.'
;
