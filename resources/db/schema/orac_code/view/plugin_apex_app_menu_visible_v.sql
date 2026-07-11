--liquibase formatted sql

--changeset clive:create_view_orac_code_view_plugin_apex_app_menu_visible_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-22
-- __description__: role-safe launchable plugin APEX app cards for APEX menu surfaces

create or replace force view orac_code.plugin_apex_app_menu_visible_v as
select plugin_id
     , plugin_version
     , app_alias
     , workspace
     , installed_app_id
     , entry_page_id
     , label
     , description
     , required_roles
     , icon
     , coalesce(card_title, label) card_title
     , card_subtitle
     , orac_code.apex_return_nav_api.launch_url(
         p_target_app_id  => installed_app_id,
         p_target_page_id => coalesce(entry_page_id, 1),
         p_request        => 'ORAC_THEME_SYNC',
         p_clear_cache    => 'RP'
       ) card_link
  from orac_code.plugin_apex_app_menu_v
 where required_roles is null
    or json_serialize(required_roles returning varchar2(4000)) = '[]'
    or exists (
         select 1
           from json_table(
                  required_roles,
                  '$[*]'
                  columns (
                    required_role varchar2(128 char) path '$'
                  )
                ) roles
          where orac_code.plugin_apex_app_auth_api.has_required_role(
                  roles.required_role,
                  v('APP_USER')
                ) = 1
       );

--rollback drop view orac_code.plugin_apex_app_menu_visible_v;
