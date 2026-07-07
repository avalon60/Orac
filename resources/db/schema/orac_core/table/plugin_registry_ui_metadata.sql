--liquibase formatted sql
-- Author: clive
-- Date: 07-Jul-2026
-- Description: Adds optional plugin UI metadata columns to the plugin registry.

--changeset clive:add_ui_metadata_columns_to_plugin_registry context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_CORE' and table_name = 'PLUGIN_REGISTRY' and column_name in ('UI_ICON_CLASS', 'UI_ACCENT_CLASS');
alter table orac_core.plugin_registry add
(
  ui_icon_class   varchar2(128 char),
  ui_accent_class varchar2(128 char)
)
;

--rollback alter table orac_core.plugin_registry drop (ui_icon_class, ui_accent_class);
