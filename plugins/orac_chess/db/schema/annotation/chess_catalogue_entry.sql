--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Annotate private catalogue management metadata.
-- Purpose: Identify source keys and JSON baselines without exposing a second reference catalogue.
-- Usage: Managed owner-only Chess plugin deployment.
--changeset clive:orac_chess_catalogue_entry_annotations context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_catalogue_entry annotations (add if not exists display_name 'Private catalogue source baselines');
alter table orac_chess.chess_catalogue_entry modify catalogue_key annotations (add if not exists display_name 'Stable source key', add if not exists semantic_role 'primary_key', add if not exists data_kind 'identifier');
alter table orac_chess.chess_catalogue_entry modify baseline_json annotations (add if not exists display_name 'Source and applied baseline', add if not exists semantic_role 'payload', add if not exists data_kind 'text');
-- Retain private metadata annotations on rollback.
--rollback empty
