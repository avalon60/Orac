--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Private source-management metadata for approved catalogue synchronisation.
-- Purpose: Preserve stable entity IDs, applied baselines and user overrides.
-- Usage: Managed Chess plugin deployment; no consumer grants.
--changeset clive:orac_chess_chs_catent_opening_uk context:plugin,prod labels:plugin stripComments:false
alter table orac_chess.chess_catalogue_entry add constraint chs_catent_opening_uk unique (opening_id);
-- Preserve private metadata integrity on rollback.
--rollback empty
