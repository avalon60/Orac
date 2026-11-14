--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_core_constraint_other_rq_req_checks context:core labels:core,relational_query stripComments:false
alter table orac_core.relational_query_requests add constraint rq_req_status_ck check (status_code in ('QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED', 'EXPIRED'));
alter table orac_core.relational_query_requests add constraint rq_req_json_ck check (result_json is json);
--rollback alter table orac_core.relational_query_requests drop constraint rq_req_status_ck;
--rollback alter table orac_core.relational_query_requests drop constraint rq_req_json_ck;
