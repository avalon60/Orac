-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Verify managed upgrades do not replay a previously successful seed batch.
-- Usage: After prepare_seed_upgrade.sql and two managed plugin upgrades, SQLcl @verify_seed_upgrade.sql
-- Run only on the separately approved isolated acceptance installation as ORAC_CHESS owner.
whenever sqlerror exit failure rollback
set serveroutput on
set define off
declare
  l_count number;
begin
  select count(*) into l_count from orac_chess.chess_video_v
  where platform = 'YouTube' and external_video_id = 'WkJKjeP0fwI';
  if l_count <> 0
  then
    raise_application_error(-20999,'Upgrade restored a user-deleted seed video');
  end if;
  select count(*) into l_count from orac_chess.chess_video_v;
  if l_count <> 43
  then
    raise_application_error(-20999,'Expected 43 remaining videos on isolated installation');
  end if;
  select count(*) into l_count from databasechangelog
  where id = 'orac_chess_seed_2026_11_07_bootstrap' and author = 'clive' and exectype = 'EXECUTED';
  if l_count <> 1
  then
    raise_application_error(-20999,'Bootstrap must have one successful once-only history entry');
  end if;
  dbms_output.put_line('PASS: repeated managed upgrade preserves user deletion and once-only history');
end;
/
