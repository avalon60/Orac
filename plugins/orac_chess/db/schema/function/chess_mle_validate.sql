--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Install private authoritative Chess MLE runtime.
-- Usage: Managed plugin deployment through pluginController.xml.

--changeset clive:orac_chess_mle_validate_call context:plugin,prod labels:plugin runOnChange:true runAlways:true stripComments:false endDelimiter:/
create or replace function orac_chess.chess_mle_validate(p_pgn clob, p_single number, p_fen varchar2) return varchar2
as mle module orac_chess.chess_mle_bridge
  env orac_chess.chess_mle_env signature 'validatePgn';
/
--rollback drop function orac_chess.chess_mle_validate;
