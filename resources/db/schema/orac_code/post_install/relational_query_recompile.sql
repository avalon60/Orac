--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Recompile Core query APIs after CODE views exist.
-- Purpose: Resolve Core CODE view ordering without optional plugin dependencies.
-- Usage: Core product/schema controller post-install phase.

--changeset clive:relational_query_recompile context:core labels:core,relational_query stripComments:false runOnChange:true runAlways:true
alter package orac_code.relational_query_api compile body;
alter package orac_code.relational_query_worker_api compile body;
--rollback alter package orac_code.relational_query_api compile body;
--rollback alter package orac_code.relational_query_worker_api compile body;
