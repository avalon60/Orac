--liquibase formatted sql

--changeset clive:preference_definitions_tapi_create_spec stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package orac_api.preference_definitions_tapi
authid definer
as
--------------------------------------------------------------------------------
--
-- Copyright (c) 2026 Clive Bostock`s Software Emporium
-- SPDX-License-Identifier: MIT
--
--------------------------------------------------------------------------------
-- Application      :   Orac
-- Domain           :   undefined
-- Package          :   preference_definitions_tapi
-- Source file name :   preference_definitions_tapi.sql
-- Purpose          :   Table API (TAPI) for table preference_definitions
--
--------------------------------------------------------------------------------

   subtype ty_row is orac_api.preference_definitions_v%rowtype;

   g_row ty_row;

   procedure ins
   (
        p_row                   in out   orac_api.preference_definitions_v%rowtype
   );

   procedure ins
   (
        p_pref_def_id           in out   orac_api.preference_definitions_v.pref_def_id%type
      , p_pref_key              in       orac_api.preference_definitions_v.pref_key%type
      , p_display_label         in       orac_api.preference_definitions_v.display_label%type
      , p_description           in       orac_api.preference_definitions_v.description%type
      , p_value_type            in       orac_api.preference_definitions_v.value_type%type
      , p_control_type          in       orac_api.preference_definitions_v.control_type%type
      , p_lov_type              in       orac_api.preference_definitions_v.lov_type%type
      , p_lov_query             in       orac_api.preference_definitions_v.lov_query%type
      , p_static_lov_code       in       orac_api.preference_definitions_v.static_lov_code%type
      , p_default_value         in       orac_api.preference_definitions_v.default_value%type
      , p_min_number            in       orac_api.preference_definitions_v.min_number%type
      , p_max_number            in       orac_api.preference_definitions_v.max_number%type
      , p_min_length            in       orac_api.preference_definitions_v.min_length%type
      , p_max_length            in       orac_api.preference_definitions_v.max_length%type
      , p_regex_pattern         in       orac_api.preference_definitions_v.regex_pattern%type
      , p_is_required           in       orac_api.preference_definitions_v.is_required%type
      , p_is_user_editable      in       orac_api.preference_definitions_v.is_user_editable%type
      , p_display_sequence      in       orac_api.preference_definitions_v.display_sequence%type
      , p_category              in       orac_api.preference_definitions_v.category%type
      , p_help_text             in       orac_api.preference_definitions_v.help_text%type
      , p_is_active             in       orac_api.preference_definitions_v.is_active%type
      , p_row_version              out   orac_api.preference_definitions_v.row_version%type
   );

   procedure get
   (
        p_pref_def_id           in       orac_api.preference_definitions_v.pref_def_id%type
      , p_row                      out   orac_api.preference_definitions_v%rowtype
   );

   procedure get
   (
        p_pref_def_id           in out   orac_api.preference_definitions_v.pref_def_id%type
      , p_pref_key                 out   orac_api.preference_definitions_v.pref_key%type
      , p_display_label            out   orac_api.preference_definitions_v.display_label%type
      , p_description              out   orac_api.preference_definitions_v.description%type
      , p_value_type               out   orac_api.preference_definitions_v.value_type%type
      , p_control_type             out   orac_api.preference_definitions_v.control_type%type
      , p_lov_type                 out   orac_api.preference_definitions_v.lov_type%type
      , p_lov_query                out   orac_api.preference_definitions_v.lov_query%type
      , p_static_lov_code          out   orac_api.preference_definitions_v.static_lov_code%type
      , p_default_value            out   orac_api.preference_definitions_v.default_value%type
      , p_min_number               out   orac_api.preference_definitions_v.min_number%type
      , p_max_number               out   orac_api.preference_definitions_v.max_number%type
      , p_min_length               out   orac_api.preference_definitions_v.min_length%type
      , p_max_length               out   orac_api.preference_definitions_v.max_length%type
      , p_regex_pattern            out   orac_api.preference_definitions_v.regex_pattern%type
      , p_is_required              out   orac_api.preference_definitions_v.is_required%type
      , p_is_user_editable         out   orac_api.preference_definitions_v.is_user_editable%type
      , p_display_sequence         out   orac_api.preference_definitions_v.display_sequence%type
      , p_category                 out   orac_api.preference_definitions_v.category%type
      , p_help_text                out   orac_api.preference_definitions_v.help_text%type
      , p_is_active                out   orac_api.preference_definitions_v.is_active%type
      , p_created_on               out   orac_api.preference_definitions_v.created_on%type
      , p_created_by               out   orac_api.preference_definitions_v.created_by%type
      , p_updated_on               out   orac_api.preference_definitions_v.updated_on%type
      , p_updated_by               out   orac_api.preference_definitions_v.updated_by%type
      , p_row_version              out   orac_api.preference_definitions_v.row_version%type
   );

   procedure upd
   (
        p_pref_def_id           in       orac_api.preference_definitions_v.pref_def_id%type
      , p_row                   in out   orac_api.preference_definitions_v%rowtype
   );

   procedure upd
   (
        p_pref_def_id           in out   orac_api.preference_definitions_v.pref_def_id%type
      , p_pref_key              in       orac_api.preference_definitions_v.pref_key%type
      , p_display_label         in       orac_api.preference_definitions_v.display_label%type
      , p_description           in       orac_api.preference_definitions_v.description%type
      , p_value_type            in       orac_api.preference_definitions_v.value_type%type
      , p_control_type          in       orac_api.preference_definitions_v.control_type%type
      , p_lov_type              in       orac_api.preference_definitions_v.lov_type%type
      , p_lov_query             in       orac_api.preference_definitions_v.lov_query%type
      , p_static_lov_code       in       orac_api.preference_definitions_v.static_lov_code%type
      , p_default_value         in       orac_api.preference_definitions_v.default_value%type
      , p_min_number            in       orac_api.preference_definitions_v.min_number%type
      , p_max_number            in       orac_api.preference_definitions_v.max_number%type
      , p_min_length            in       orac_api.preference_definitions_v.min_length%type
      , p_max_length            in       orac_api.preference_definitions_v.max_length%type
      , p_regex_pattern         in       orac_api.preference_definitions_v.regex_pattern%type
      , p_is_required           in       orac_api.preference_definitions_v.is_required%type
      , p_is_user_editable      in       orac_api.preference_definitions_v.is_user_editable%type
      , p_display_sequence      in       orac_api.preference_definitions_v.display_sequence%type
      , p_category              in       orac_api.preference_definitions_v.category%type
      , p_help_text             in       orac_api.preference_definitions_v.help_text%type
      , p_is_active             in       orac_api.preference_definitions_v.is_active%type
      , p_row_version              out   orac_api.preference_definitions_v.row_version%type
   );

   procedure del
   (
        p_pref_def_id           in out   orac_api.preference_definitions_v.pref_def_id%type
      , p_row_version              out   orac_api.preference_definitions_v.row_version%type
   );

end preference_definitions_tapi;
/
--rollback drop package orac_api.preference_definitions_tapi;