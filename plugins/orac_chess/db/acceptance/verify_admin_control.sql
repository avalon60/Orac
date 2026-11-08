-- Author: Clive Bostock
-- Date: 02-Nov-2026
-- Purpose: Verify DEV-only persisted controls and disabled-plugin gate with complete rollback.
-- Usage: sql -name orac-db @plugins/orac_chess/db/acceptance/verify_admin_control.sql
-- Privileged configuration companion; never run through the parsing-schema connection.
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on
set define off
declare
  l_app number;
  l_blob blob;
  l_raw raw(32767);
  l_image number;
  l_version number;
  l_limit number;
  l_after number;
begin
  if user!='SYSTEM' or sys_context('userenv','con_name')!='FREEPDB1' then raise_application_error(-20998,'Wrong control-test target'); end if;
  select application_id into l_app from apex_applications where alias='ORAC_CHESS_ADMIN' and workspace='ORAC' and owner='ORAC_APX_PUB';
  if orac_code.plugin_apex_app_auth_api.plugin_is_available('orac_chess',l_app)!=1 then
    raise_application_error(-20999,'Run control checks after successful deployment; initial availability must be true');
  end if;
  savepoint chess_authorization_gate;
  orac_code.plugin_registry_api.set_enabled('orac_chess','N');
  if orac_code.plugin_apex_app_auth_api.plugin_is_available('orac_chess',l_app)!=0 then
    raise_application_error(-20999,'Disabled plugin gate accepted');
  end if;
  rollback to chess_authorization_gate;
  if orac_code.plugin_apex_app_auth_api.plugin_is_available('orac_chess',l_app)!=1 then
    raise_application_error(-20999,'Plugin state not restored after rollback');
  end if;
  select max_image_bytes into l_limit from orac_chess.chess_admin_control where control_id=1;
  savepoint chess_image_limit;
  update orac_chess.chess_admin_control set max_image_bytes=10 where control_id=1;
  dbms_lob.createtemporary(l_blob,true);
  l_raw:=hextoraw('89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000D49444154789C63606060F80F00010401005FE5C34B0000000049454E44AE426082');
  dbms_lob.writeappend(l_blob,utl_raw.length(l_raw),l_raw);
  begin
    orac_chess.chess_image_api.save_image(l_image,null,'pixel.png','image/png',null,'Test pixel',l_blob,l_version);
    raise_application_error(-20999,'Persisted upload limit bypassed');
  exception when others then if sqlcode!=-20006 then raise; end if; end;
  begin
    update orac_chess.chess_admin_control set max_image_bytes=0 where control_id=1;
    raise_application_error(-20999,'Nonpositive upload limit accepted');
  exception when others then if sqlcode!=-2290 then raise; end if; end;
  begin
    update orac_chess.chess_admin_control set max_image_bytes=1.5 where control_id=1;
    raise_application_error(-20999,'Fractional upload limit accepted');
  exception when others then if sqlcode!=-2290 then raise; end if; end;
  rollback to chess_image_limit;
  select max_image_bytes into l_after from orac_chess.chess_admin_control where control_id=1;
  if l_after!=l_limit then raise_application_error(-20999,'Persisted limit not restored'); end if;
  dbms_lob.freetemporary(l_blob);
  rollback;
  dbms_output.put_line('CHESS_ADMIN_CONTROL_PASSED');
exception when others then rollback;raise;
end;
/
exit
