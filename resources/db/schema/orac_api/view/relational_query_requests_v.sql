--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_api_view_relational_query_requests_v context:core labels:core,relational_query stripComments:false runOnChange:true
create or replace view orac_api.relational_query_requests_v as
select request_id, username, application_id, apex_session_id, dataset_id, metadata_version, manifest_hash, question, status_code, lease_owner, lease_token, lease_expires_on, result_json, failure_code, created_on, expires_on
from orac_core.relational_query_requests;
--rollback drop view orac_api.relational_query_requests_v;
