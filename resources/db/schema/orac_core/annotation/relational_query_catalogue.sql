--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Classify internal relational query persistence.
-- Purpose: Mark lifecycle, payload and operational audit as non-queryable.
-- Usage: Production orac_core typed schema controller.

--changeset clive:relational_query_annotate_relational_query_catalogue context:core labels:core,relational_query stripComments:false runOnChange:true
alter table orac_core.relational_query_catalogue annotations (
  add if not exists display_name 'Relational query catalogue',
  add if not exists ai_queryable 'N',
  add if not exists sensitivity 'internal'
);
--rollback alter table orac_core.relational_query_catalogue annotations (drop display_name, drop ai_queryable, drop sensitivity);
