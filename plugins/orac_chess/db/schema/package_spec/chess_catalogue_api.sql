--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Private source-management metadata for approved catalogue synchronisation.
-- Purpose: Preserve stable entity IDs, applied baselines and user overrides.
-- Usage: Managed Chess plugin deployment; no consumer grants.
--changeset clive:orac_chess_catalogue_api_spec context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package orac_chess.chess_catalogue_api authid definer as
  -- Private owner-only operations. Planning performs no DML or temporary fixture writes.
  procedure plan_catalogue(p_payload clob,p_report out clob);
  procedure apply_catalogue(p_payload clob,p_report out clob);
end chess_catalogue_api;
/
--rollback empty
