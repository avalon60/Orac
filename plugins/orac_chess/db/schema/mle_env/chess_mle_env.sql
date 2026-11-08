--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Install private authoritative Chess MLE runtime.
-- Usage: Managed plugin deployment through pluginController.xml.

--changeset clive:orac_chess_mle_env context:plugin,prod labels:plugin runOnChange:true runAlways:true stripComments:false
create or replace mle env orac_chess.chess_mle_env
imports (
  'orac-chess-lib' module orac_chess.chess_mle_lib,
  'orac-chess-policy' module orac_chess.chess_mle_policy
) pure;
--rollback drop mle env orac_chess.chess_mle_env;
