--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Classify internal relational query persistence.
-- Purpose: Mark lifecycle, payload and operational audit as non-queryable.
-- Usage: Production orac_core typed schema controller.

--changeset clive:relational_query_audit_json_ck context:core labels:core,relational_query stripComments:false
alter table orac_core.relational_query_audit add constraint rq_aud_json_ck check(event_json is json);
--rollback alter table orac_core.relational_query_audit drop constraint rq_aud_json_ck;
