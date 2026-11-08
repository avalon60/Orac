--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Indexes chess_gambit by name.
-- Purpose: Install the index object chs_gmb_name_ux in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_index_chs_gmb_name_ux context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CHESS' and index_name = 'CHS_GMB_NAME_UX'
create unique index orac_chess.chs_gmb_name_ux on orac_chess.chess_gambit (name);

--rollback drop index orac_chess.chs_gmb_name_ux;
