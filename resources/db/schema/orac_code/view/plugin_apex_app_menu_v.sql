-- __author__: clive
-- __date__: 2026-06-20
-- __description__: launchable plugin APEX apps for future admin menu surfaces

create or replace view orac_code.plugin_apex_app_menu_v as
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
  from orac_api.plugin_apex_apps_v
 where enabled = 'Y'
   and install_status = 'installed'
   and installed_app_id is not null;
