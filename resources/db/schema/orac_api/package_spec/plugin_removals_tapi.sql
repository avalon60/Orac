--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plugin_removals_tapi_spec context:core labels:core stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package orac_api.plugin_removals_tapi authid definer as
  procedure ins(p_row in out orac_api.plugin_removals_v%rowtype);
  procedure checkpoint(p_removal_id in varchar2, p_checkpoints in json,
    p_external_complete_yn in varchar2, p_files_complete_yn in varchar2,
    p_error_code in varchar2 default null, p_error_message in varchar2 default null);
  procedure complete(p_removal_id in varchar2);
end plugin_removals_tapi;
/
--rollback drop package orac_api.plugin_removals_tapi;
