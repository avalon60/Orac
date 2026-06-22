--liquibase formatted sql

--changeset clive:comment_orac_core_comment_preference_definitions context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.preference_definitions is
  'Defines preference metadata, including display, validation, and LOV behaviour for user-editable settings.'
;

comment on column orac_core.preference_definitions.pref_def_id is
  'Primary key for the preference definition row.'
;

comment on column orac_core.preference_definitions.pref_key is
  'Unique logical preference key used by user preference rows.'
;

comment on column orac_core.preference_definitions.display_label is
  'Human-readable label presented in user interfaces.'
;

comment on column orac_core.preference_definitions.description is
  'Optional internal description of the preference.'
;

comment on column orac_core.preference_definitions.value_type is
  'Logical data type for stored preference values.'
;

comment on column orac_core.preference_definitions.control_type is
  'Preferred UI control type for editing the preference, such as text, select_list, or popup_lov.'
;

comment on column orac_core.preference_definitions.lov_type is
  'LOV source type when the preference is backed by a selectable list.'
;

comment on column orac_core.preference_definitions.lov_query is
  'Optional SQL query used to populate a dynamic LOV.'
;

comment on column orac_core.preference_definitions.static_lov_code is
  'Optional code identifying a static LOV definition.'
;

comment on column orac_core.preference_definitions.default_value is
  'Default value expressed as JSON.'
;

comment on column orac_core.preference_definitions.min_number is
  'Optional minimum numeric value constraint.'
;

comment on column orac_core.preference_definitions.max_number is
  'Optional maximum numeric value constraint.'
;

comment on column orac_core.preference_definitions.min_length is
  'Optional minimum text length constraint.'
;

comment on column orac_core.preference_definitions.max_length is
  'Optional maximum text length constraint.'
;

comment on column orac_core.preference_definitions.regex_pattern is
  'Optional regular expression used to validate text values.'
;

comment on column orac_core.preference_definitions.is_required is
  'Indicates whether a value is required for this preference.'
;

comment on column orac_core.preference_definitions.is_user_editable is
  'Indicates whether end users may edit this preference directly.'
;

comment on column orac_core.preference_definitions.display_sequence is
  'Display ordering used when presenting preferences in the UI.'
;

comment on column orac_core.preference_definitions.category is
  'Optional UI grouping category for the preference.'
;

comment on column orac_core.preference_definitions.help_text is
  'Optional help text shown to users when editing the preference.'
;

comment on column orac_core.preference_definitions.is_active is
  'Indicates whether this preference definition is active and available.'
;

comment on column orac_core.preference_definitions.created_on is
  'Timestamp when the record was created.'
;

comment on column orac_core.preference_definitions.created_by is
  'User or process that created the record.'
;

comment on column orac_core.preference_definitions.updated_on is
  'Timestamp when the record was last updated.'
;

comment on column orac_core.preference_definitions.updated_by is
  'User or process that last updated the record.'
;

comment on column orac_core.preference_definitions.row_version is
  'Row version number used for optimistic locking.'
;
