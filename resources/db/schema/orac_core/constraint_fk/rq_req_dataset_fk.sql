--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Classify internal relational query persistence.
-- Purpose: Mark lifecycle, payload and operational audit as non-queryable.
-- Usage: Production orac_core typed schema controller.

--changeset clive:relational_query_request_dataset_fk context:core labels:core,relational_query stripComments:false
alter table orac_core.relational_query_requests add constraint rq_req_dataset_fk
  foreign key (dataset_id) references orac_core.relational_query_catalogue(dataset_id);
--rollback alter table orac_core.relational_query_requests drop constraint rq_req_dataset_fk;
