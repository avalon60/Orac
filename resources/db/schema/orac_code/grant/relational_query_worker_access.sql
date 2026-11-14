--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_code_grant_relational_query_worker_access context:core labels:core,relational_query stripComments:false runOnChange:true
grant execute on orac_code.relational_query_worker_api to orac;
--rollback revoke execute on orac_code.relational_query_worker_api from orac;
