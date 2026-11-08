--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Creates the chess_image_variation table.
-- Purpose: Install the table object chess_image_variation in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_table_chess_image_variation context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CHESS' and table_name = 'CHESS_IMAGE_VARIATION'
create table orac_chess.chess_image_variation
(
  image_id                 number not null,
  variation_id             number not null
)
logging
no inmemory;

--rollback drop table orac_chess.chess_image_variation;
