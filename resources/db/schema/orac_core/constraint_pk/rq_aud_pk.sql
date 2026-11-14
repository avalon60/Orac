--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_core_constraint_pk_rq_aud_pk context:core labels:core,relational_query stripComments:false
alter table orac_core.relational_query_audit add constraint rq_aud_pk primary key (audit_id);
--rollback alter table orac_core.relational_query_audit drop constraint rq_aud_pk;
