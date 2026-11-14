--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_core_index_rq_req_queue_ix context:core labels:core,relational_query stripComments:false
create index orac_core.rq_req_queue_ix on orac_core.relational_query_requests(status_code, created_on);
--rollback drop index orac_core.rq_req_queue_ix;
