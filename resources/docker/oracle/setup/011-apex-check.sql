prompt Checking APEX Installation
alter session set container=FREEPDB1;
column comp_id format a20
column version format a10
select comp_id, version from dba_registry
where comp_id = 'APEX';
spool off
