--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Reject installation with invalid relational query APIs.
-- Purpose: Make query package compilation failures propagate to installation.
-- Usage: Core CODE schema post-install controller.

--changeset clive:relational_query_validate_code context:core labels:core,relational_query stripComments:false runOnChange:true runAlways:true splitStatements:false endDelimiter:/
declare
  l_count number;
begin
  select count(*) into l_count from all_objects
   where owner='ORAC_CODE'
     and object_name in ('RELATIONAL_QUERY_API','RELATIONAL_QUERY_WORKER_API')
     and object_type in ('PACKAGE','PACKAGE BODY') and status='VALID';
  if l_count<>4
  then
    raise_application_error(-20895,'QUERY_CORE_API_COMPILATION_UNVERIFIED');
  end if;
end;
/
--rollback select 1 from dual;
