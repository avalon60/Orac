--liquibase formatted sql

--changeset clive:preference_definitions_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.preference_definitions_v as
   select
        pref_def_id
      , pref_key
      , display_label
      , description
      , value_type
      , control_type
      , lov_type
      , lov_query
      , static_lov_code
      , default_value
      , min_number
      , max_number
      , step_number
      , unit_label
      , display_min_label
      , display_max_label
      , display_value_format
      , min_length
      , max_length
      , regex_pattern
      , is_required
      , is_user_editable
      , display_sequence
      , category
      , help_text
      , is_active
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
     from orac_core.preference_definitions;
--rollback drop view orac_api.preference_definitions_v;
