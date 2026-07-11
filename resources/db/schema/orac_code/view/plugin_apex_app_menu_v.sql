--liquibase formatted sql

--changeset clive:create_view_orac_code_view_plugin_apex_app_menu_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: launchable plugin APEX apps for future admin menu surfaces

create or replace force view orac_code.plugin_apex_app_menu_v as
select app.plugin_id
     , app.plugin_version
     , app.app_alias
     , app.workspace
     , app.installed_app_id
     , app.entry_page_id
     , app.label
     , app.description
     , app.required_roles
     , coalesce(app.icon, plugin.ui_icon_class, 'fa fa-plug') as icon
     , coalesce(app.card_title, app.label) card_title
     , app.card_subtitle
  from orac_api.plugin_apex_apps_v app
  left join orac_code.plugin_registry_v plugin
    on plugin.plugin_id = app.plugin_id
 where app.enabled = 'Y'
   and app.install_status = 'installed'
   and app.installed_app_id is not null;

--rollback drop view orac_code.plugin_apex_app_menu_v;
