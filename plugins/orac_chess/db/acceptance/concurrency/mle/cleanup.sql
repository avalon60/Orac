-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Verify serialised production MLE hierarchy writes with isolated fixtures.
-- Usage: Approved DEV consumer SQLcl; setup, session A, session B, then cleanup.
-- Setup/cleanup explicitly COMMIT only reserved __MLE_CONC_ fixture records.
whenever sqlerror exit failure rollback
set define off
set serveroutput on
declare
  l_owner number;
  l_version number;
begin
  if user<>'ORAC_APX_PUB' or sys_context('userenv','con_name')<>'FREEPDB1' then raise_application_error(-20998,'Wrong DEV concurrency principal'); end if;
  for owner_row in (select opening_id,row_version from orac_chess.chess_opening_v where name in ('__MLE_CONC_PARENT','__MLE_CONC_ROOTS')) loop
    for child in (select variation_id,row_version from orac_chess.chess_variation_v where opening_id=owner_row.opening_id and parent_variation_id is not null) loop
      orac_chess.chess_variation_api.delete_variation(child.variation_id,child.row_version);
    end loop;
    for main in (select variation_id,row_version from orac_chess.chess_variation_v where opening_id=owner_row.opening_id) loop
      orac_chess.chess_variation_api.delete_variation(main.variation_id,main.row_version);
    end loop;
    orac_chess.chess_admin_api.delete_opening(owner_row.opening_id,owner_row.row_version);
  end loop;
end;
/
commit;
prompt CHESS_MLE_CONCURRENCY_FIXTURES_REMOVED
exit
