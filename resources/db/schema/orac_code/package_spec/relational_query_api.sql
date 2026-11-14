--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_code_package_spec_relational_query_api context:core labels:core,relational_query stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package orac_code.relational_query_api authid definer as
  procedure submit_query(p_dataset_id in varchar2, p_question in varchar2, p_request_id out number);
  procedure read_query(p_request_id in number, p_status out varchar2, p_result out clob);
end relational_query_api;
/
--rollback drop package orac_code.relational_query_api;
