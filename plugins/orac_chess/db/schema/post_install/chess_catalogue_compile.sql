--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Fail deployment if the private catalogue API is invalid.
-- Purpose: Verify newly installed sync runtime before catalogue application.
-- Usage: Managed Chess plugin deployment after catalogue package bodies.
--changeset clive:orac_chess_catalogue_strategy_recompile context:plugin,prod labels:plugin stripComments:false runAlways:true runOnChange:true
alter package orac_chess.chess_catalogue_api compile body;
--rollback empty

--changeset clive:orac_chess_catalogue_compile context:plugin,prod labels:plugin stripComments:false runAlways:true runOnChange:true endDelimiter:/
declare
  l_count number;
begin
  select count(*) into l_count from user_objects where object_name='CHESS_CATALOGUE_API' and status!='VALID';
  if l_count!=0 then raise_application_error(-20020,'Private catalogue API compilation failed; inspect USER_ERRORS.'); end if;
end;
/
--rollback empty
