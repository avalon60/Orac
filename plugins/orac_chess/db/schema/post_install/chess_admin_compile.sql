--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Recompile dependent administration bodies after replaceable specifications.
-- Purpose: Prevent unchanged bodies remaining invalid after a specification upgrade.
-- Usage: Final managed plugin controller pass; no data or transaction mutations.

--changeset clive:orac_chess_admin_compile_chess_validation_api context:plugin,prod labels:plugin runAlways:true runOnChange:true stripComments:false
alter package orac_chess.chess_validation_api compile body;
-- Compilation has no inverse; the package object's rollback owns removal.
--rollback select 1 from dual;

--changeset clive:orac_chess_admin_compile_chess_admin_tapi context:plugin,prod labels:plugin runAlways:true runOnChange:true stripComments:false
alter package orac_chess.chess_admin_tapi compile body;
-- Compilation has no inverse; the package object's rollback owns removal.
--rollback select 1 from dual;

--changeset clive:orac_chess_admin_compile_chess_admin_api context:plugin,prod labels:plugin runAlways:true runOnChange:true stripComments:false
alter package orac_chess.chess_admin_api compile body;
-- Compilation has no inverse; the package object's rollback owns removal.
--rollback select 1 from dual;

--changeset clive:orac_chess_admin_compile_chess_game_api context:plugin,prod labels:plugin runAlways:true runOnChange:true stripComments:false
alter package orac_chess.chess_game_api compile body;
-- Compilation has no inverse; the package object's rollback owns removal.
--rollback select 1 from dual;

--changeset clive:orac_chess_admin_compile_chess_variation_api context:plugin,prod labels:plugin runAlways:true runOnChange:true stripComments:false
alter package orac_chess.chess_variation_api compile body;
-- Compilation has no inverse; the package object's rollback owns removal.
--rollback select 1 from dual;

--changeset clive:orac_chess_admin_compile_chess_image_api context:plugin,prod labels:plugin runAlways:true runOnChange:true stripComments:false
alter package orac_chess.chess_image_api compile body;
-- Compilation has no inverse; the package object's rollback owns removal.
--rollback select 1 from dual;

--changeset clive:orac_chess_mle_assert_valid context:plugin,prod labels:plugin runAlways:true runOnChange:true stripComments:false endDelimiter:/
declare
  l_count pls_integer;
begin
  select count(*) into l_count from user_objects
  where object_name in ('CHESS_MLE_LIB','CHESS_MLE_POLICY','CHESS_MLE_BRIDGE',
    'CHESS_MLE_ENV','CHESS_MLE_VALIDATE','CHESS_MLE_BRANCH','CHESS_MLE_CONTINUATION','CHESS_MLE_HEADER',
    'CHESS_VALIDATION_API','CHESS_ADMIN_TAPI','CHESS_ADMIN_API','CHESS_GAME_API',
    'CHESS_VARIATION_API','CHESS_IMAGE_API') and status<>'VALID';
  if l_count<>0
  then
    raise_application_error(-20020,'Chess runtime or API compilation failed.');
  end if;
  if chess_mle_continuation(to_clob('1.e4 *'),to_clob('1.e4 e5 *'),1,null) is not null
    or chess_mle_continuation(to_clob('1.e4 *'),to_clob('1.d4 d5 *'),1,null) is null
  then
    raise_application_error(-20020,'Chess continuation semantic smoke failed.');
  end if;
  if chess_mle_validate(to_clob('1.e4 *'),0,null) is not null
  then
    raise_application_error(-20020,'Chess runtime semantic smoke failed.');
  end if;
end;
/
--rollback select 1 from dual;
