--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Privileged schema provisioning and removal receipts.

--changeset clive:create_plugin_schema_ownership_tapi_spec context:core labels:core stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package orac_api.plugin_schema_ownership_tapi authid definer as
  procedure ins(p_row in out orac_api.plugin_schema_ownership_v%rowtype);
  procedure record_disposition(p_schema_ownership_id in number, p_removal_id in varchar2,
    p_disposition in varchar2);
end plugin_schema_ownership_tapi;
/
--rollback drop package orac_api.plugin_schema_ownership_tapi;
