--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 12-Nov-2026
-- Description: Separate instructional strategy from historical descriptions.
-- Purpose: Add nullable strategy without rewriting catalogue identities or content.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_opening_strategy context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_OPENING' and column_name='STRATEGY'
alter table orac_chess.chess_opening add (strategy clob);
comment on column orac_chess.chess_opening.strategy is 'Original instructional plans grounded in the catalogue reference position; independent of description.';
-- Content is retained: forward correction is preferred to dropping authored strategy.
--rollback empty

--changeset clive:orac_chess_gambit_strategy context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_GAMBIT' and column_name='STRATEGY'
alter table orac_chess.chess_gambit add (strategy clob);
comment on column orac_chess.chess_gambit.strategy is 'Original instructional plans grounded in the catalogue reference position; independent of description.';
-- Content is retained: forward correction is preferred to dropping authored strategy.
--rollback empty

