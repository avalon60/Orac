-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Fail closed before removing private MLE; retain all data and history.
-- Usage: Approved owner/admin SQLcl @plugins/orac_chess/db/recovery/mle/withdraw.sql
-- First import apex/recovery/orac_chess_admin_readonly.sql through the host receipt path.
-- Preserve the currently installed app ID; this script does not import APEX.
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off
set sqlblanklines on
begin
  if sys_context('userenv','session_user') not in ('ORAC_CHESS','SYSTEM')
     or sys_context('userenv','con_name')<>'FREEPDB1'
  then
    raise_application_error(-20998,'Wrong approved withdrawal target');
  end if;
end;
/
@@chess_game_api.sql
@@chess_variation_api.sql
@@chess_validation_api.sql
alter package orac_chess.chess_admin_tapi compile body;
alter package orac_chess.chess_game_api compile body;
alter package orac_chess.chess_variation_api compile body;
declare
  l_count number;
begin
  select count(*) into l_count from all_objects where owner='ORAC_CHESS'
  and object_name in ('CHESS_VALIDATION_API','CHESS_ADMIN_TAPI','CHESS_GAME_API','CHESS_VARIATION_API')
  and status<>'VALID';
  if l_count<>0 then raise_application_error(-20020,'Recovery API compilation failed; MLE retained'); end if;
end;
/
drop function orac_chess.chess_mle_header;
drop function orac_chess.chess_mle_branch;
drop function orac_chess.chess_mle_validate;
drop mle env orac_chess.chess_mle_env;
drop mle module orac_chess.chess_mle_bridge;
drop mle module orac_chess.chess_mle_policy;
drop mle module orac_chess.chess_mle_lib;
-- No privilege revocation: a pre-existing owner grant must not be removed blindly.
prompt CHESS_MLE_WITHDRAWN_DATA_AND_HISTORY_RETAINED
