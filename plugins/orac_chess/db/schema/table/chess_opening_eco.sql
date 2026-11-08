--liquibase formatted sql
-- Author: clive
-- Date: 01-Nov-2026
-- Description: Creates the chess_opening_eco table.
-- Purpose: Install the table object chess_opening_eco in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_table_chess_opening_eco context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CHESS' and table_name = 'CHESS_OPENING_ECO'
create table orac_chess.chess_opening_eco
(
  opening_id               number not null,
  eco_code                 varchar2(3 char) not null
)
logging
no inmemory;

--rollback drop table orac_chess.chess_opening_eco;
