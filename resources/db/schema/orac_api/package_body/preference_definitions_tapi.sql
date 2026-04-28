--liquibase formatted sql

--changeset clive:preference_definitions_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true

create or replace package body orac_api.preference_definitions_tapi
as
   procedure ins
   (
        p_row                   in out   orac_api.preference_definitions_v%rowtype
   )
   is
   begin
      insert into orac_api.preference_definitions_v
         (
              pref_key
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
            , min_length
            , max_length
            , regex_pattern
            , is_required
            , is_user_editable
            , display_sequence
            , category
            , help_text
            , is_active
         )
      values
         (
              p_row.pref_key
            , p_row.display_label
            , p_row.description
            , p_row.value_type
            , p_row.control_type
            , p_row.lov_type
            , p_row.lov_query
            , p_row.static_lov_code
            , p_row.default_value
            , p_row.min_number
            , p_row.max_number
            , p_row.min_length
            , p_row.max_length
            , p_row.regex_pattern
            , p_row.is_required
            , p_row.is_user_editable
            , p_row.display_sequence
            , p_row.category
            , p_row.help_text
            , p_row.is_active
         )
      ;

      select pref_def_id
           , row_version
        into p_row.pref_def_id
           , p_row.row_version
        from orac_api.preference_definitions_v
       where pref_key = p_row.pref_key;

   end ins;

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
   )
   is
   begin
      insert into orac_api.preference_definitions_v
         (
              pref_key
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
            , min_length
            , max_length
            , regex_pattern
            , is_required
            , is_user_editable
            , display_sequence
            , category
            , help_text
            , is_active
         )
      values
         (
              p_pref_key
            , p_display_label
            , p_description
            , p_value_type
            , p_control_type
            , p_lov_type
            , p_lov_query
            , p_static_lov_code
            , p_default_value
            , p_min_number
            , p_max_number
            , p_min_length
            , p_max_length
            , p_regex_pattern
            , p_is_required
            , p_is_user_editable
            , p_display_sequence
            , p_category
            , p_help_text
            , p_is_active
         )
      ;

      select pref_def_id
           , row_version
        into p_pref_def_id
           , p_row_version
        from orac_api.preference_definitions_v
       where pref_key = p_pref_key;

   end ins;

   procedure get
   (
        p_pref_def_id           in       orac_api.preference_definitions_v.pref_def_id%type
      , p_row                      out   orac_api.preference_definitions_v%rowtype
   )
   is
   begin
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
        into
           p_row.pref_def_id
         , p_row.pref_key
         , p_row.display_label
         , p_row.description
         , p_row.value_type
         , p_row.control_type
         , p_row.lov_type
         , p_row.lov_query
         , p_row.static_lov_code
         , p_row.default_value
         , p_row.min_number
         , p_row.max_number
         , p_row.min_length
         , p_row.max_length
         , p_row.regex_pattern
         , p_row.is_required
         , p_row.is_user_editable
         , p_row.display_sequence
         , p_row.category
         , p_row.help_text
         , p_row.is_active
         , p_row.created_on
         , p_row.created_by
         , p_row.updated_on
         , p_row.updated_by
         , p_row.row_version
       from orac_api.preference_definitions_v
      where pref_def_id = p_pref_def_id;

   end get;

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
   )
   is
   begin
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
        into
           p_pref_def_id
         , p_pref_key
         , p_display_label
         , p_description
         , p_value_type
         , p_control_type
         , p_lov_type
         , p_lov_query
         , p_static_lov_code
         , p_default_value
         , p_min_number
         , p_max_number
         , p_min_length
         , p_max_length
         , p_regex_pattern
         , p_is_required
         , p_is_user_editable
         , p_display_sequence
         , p_category
         , p_help_text
         , p_is_active
         , p_created_on
         , p_created_by
         , p_updated_on
         , p_updated_by
         , p_row_version
       from orac_api.preference_definitions_v
      where pref_def_id = p_pref_def_id;

   end get;

   procedure upd
   (
        p_pref_def_id           in       orac_api.preference_definitions_v.pref_def_id%type
      , p_row                   in out   orac_api.preference_definitions_v%rowtype
   )
   is
   begin
      update orac_api.preference_definitions_v
         set pref_key         = p_row.pref_key
           , display_label    = p_row.display_label
           , description      = p_row.description
           , value_type       = p_row.value_type
           , control_type     = p_row.control_type
           , lov_type         = p_row.lov_type
           , lov_query        = p_row.lov_query
           , static_lov_code  = p_row.static_lov_code
           , default_value    = p_row.default_value
           , min_number       = p_row.min_number
           , max_number       = p_row.max_number
           , min_length       = p_row.min_length
           , max_length       = p_row.max_length
           , regex_pattern    = p_row.regex_pattern
           , is_required      = p_row.is_required
           , is_user_editable = p_row.is_user_editable
           , display_sequence = p_row.display_sequence
           , category         = p_row.category
           , help_text        = p_row.help_text
           , is_active        = p_row.is_active
       where pref_def_id = p_pref_def_id;

      p_row.pref_def_id := p_pref_def_id;

      select row_version
        into p_row.row_version
        from orac_api.preference_definitions_v
       where pref_def_id = p_pref_def_id;

   end upd;

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
   )
   is
   begin
      update orac_api.preference_definitions_v
         set pref_key         = p_pref_key
           , display_label    = p_display_label
           , description      = p_description
           , value_type       = p_value_type
           , control_type     = p_control_type
           , lov_type         = p_lov_type
           , lov_query        = p_lov_query
           , static_lov_code  = p_static_lov_code
           , default_value    = p_default_value
           , min_number       = p_min_number
           , max_number       = p_max_number
           , min_length       = p_min_length
           , max_length       = p_max_length
           , regex_pattern    = p_regex_pattern
           , is_required      = p_is_required
           , is_user_editable = p_is_user_editable
           , display_sequence = p_display_sequence
           , category         = p_category
           , help_text        = p_help_text
           , is_active        = p_is_active
       where pref_def_id = p_pref_def_id;

      select row_version
        into p_row_version
        from orac_api.preference_definitions_v
       where pref_def_id = p_pref_def_id;

   end upd;

   procedure del
   (
        p_pref_def_id           in out   orac_api.preference_definitions_v.pref_def_id%type
      , p_row_version              out   orac_api.preference_definitions_v.row_version%type
   )
   is
   begin
      select row_version
        into p_row_version
        from orac_api.preference_definitions_v
       where pref_def_id = p_pref_def_id;

      delete
        from orac_api.preference_definitions_v
       where pref_def_id = p_pref_def_id;

   end del;

end preference_definitions_tapi;
/
--rollback drop package body orac_api.preference_definitions_tapi
