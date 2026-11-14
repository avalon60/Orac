--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_code_package_spec_relational_query_worker_api context:core labels:core,relational_query stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package orac_code.relational_query_worker_api authid definer as
  procedure sync_dataset(p_dataset_id in varchar2, p_plugin_id in varchar2, p_metadata_version in varchar2,
                         p_manifest_hash in varchar2, p_declaration in clob);
  function dataset_available(p_dataset_id in varchar2, p_metadata_version in varchar2, p_manifest_hash in varchar2) return number;
  function reviewed_metadata(p_dataset_id in varchar2, p_metadata_version in varchar2,
                             p_manifest_hash in varchar2) return clob;
  procedure claim_next(p_worker in varchar2, p_request_id out number, p_lease out varchar2,
                       p_username out varchar2, p_dataset out varchar2, p_question out varchar2);
  procedure complete_query(p_request_id in number, p_worker in varchar2, p_lease in varchar2,
                           p_result in clob, p_failure in varchar2 default null);
  procedure audit_event(p_event in clob);
  procedure reserve_query(p_username in varchar2, p_dataset in varchar2, p_existing_id in number, p_token out number);
  procedure release_query(p_token in number);
  procedure purge_expired;
end relational_query_worker_api;
/
--rollback drop package orac_code.relational_query_worker_api;
