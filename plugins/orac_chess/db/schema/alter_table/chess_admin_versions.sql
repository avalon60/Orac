--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_opening_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_OPENING' and column_name='ROW_VERSION'
alter table orac_chess.chess_opening add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_opening drop column row_version;

--changeset clive:orac_chess_admin_gambit_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_GAMBIT' and column_name='ROW_VERSION'
alter table orac_chess.chess_gambit add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_gambit drop column row_version;

--changeset clive:orac_chess_admin_variation_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_VARIATION' and column_name='ROW_VERSION'
alter table orac_chess.chess_variation add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_variation drop column row_version;

--changeset clive:orac_chess_admin_video_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_VIDEO' and column_name='ROW_VERSION'
alter table orac_chess.chess_video add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_video drop column row_version;

--changeset clive:orac_chess_admin_concept_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_CONCEPT' and column_name='ROW_VERSION'
alter table orac_chess.chess_concept add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_concept drop column row_version;

--changeset clive:orac_chess_admin_game_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_GAME' and column_name='ROW_VERSION'
alter table orac_chess.chess_game add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_game drop column row_version;

--changeset clive:orac_chess_admin_commentary_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_COMMENTARY' and column_name='ROW_VERSION'
alter table orac_chess.chess_commentary add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_commentary drop column row_version;

--changeset clive:orac_chess_admin_image_row_version context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_IMAGE' and column_name='ROW_VERSION'
alter table orac_chess.chess_image add (row_version number default 1 not null);
--rollback alter table orac_chess.chess_image drop column row_version;
