--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Private source-management metadata for approved catalogue synchronisation.
-- Purpose: Preserve stable entity IDs, applied baselines and user overrides.
-- Usage: Managed Chess plugin deployment; no consumer grants.
--changeset clive:orac_chess_catalogue_entry context:plugin,prod labels:plugin stripComments:false
create table orac_chess.chess_catalogue_entry (
  catalogue_key varchar2(100 char) not null,
  entity_kind varchar2(12 char) not null,
  opening_id number,
  gambit_id number,
  variation_id number,
  ownership varchar2(7 char) not null,
  source_revision varchar2(100 char) not null,
  last_source_hash raw(32) not null,
  baseline_json clob not null
);
-- Preserve metadata and tombstones on rollback.
--rollback empty
