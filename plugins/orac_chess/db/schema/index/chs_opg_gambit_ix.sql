--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Indexes chess_opening_gambit by gambit_id.
-- Purpose: Install the index object chs_opg_gambit_ix in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_index_chs_opg_gambit_ix context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CHESS' and index_name = 'CHS_OPG_GAMBIT_IX'
create index orac_chess.chs_opg_gambit_ix on orac_chess.chess_opening_gambit (gambit_id);

--rollback drop index orac_chess.chs_opg_gambit_ix;
