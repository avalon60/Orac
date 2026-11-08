-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Delete one bootstrap video in an expressly isolated upgrade acceptance installation.
-- Usage: Set client_identifier to ORAC_CHESS_SEED_ISOLATED_ACCEPTANCE; SQLcl @prepare_seed_upgrade.sql
-- Intentionally commits the test deletion so the next managed upgrade must preserve it.
-- Never include in controllers or run against existing DEV data.
whenever sqlerror exit failure rollback
set define off
declare
  l_id number;
  l_version number;
begin
  if sys_context('userenv','client_identifier') <> 'ORAC_CHESS_SEED_ISOLATED_ACCEPTANCE'
     or sys_context('userenv','client_identifier') is null
  then
    raise_application_error(-20998,'Requires explicit isolated seed acceptance opt-in');
  end if;
  select video_id,row_version into l_id,l_version from orac_chess.chess_video_v
  where platform = 'YouTube' and external_video_id = 'WkJKjeP0fwI';
  orac_chess.chess_admin_api.delete_video(l_id,l_version);
  commit;
end;
/
