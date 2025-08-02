spool /var/tmp/dapex/log/apex_install.log append
select comp_id, version from dba_registry
where comp_id = 'APEX';
spool off
exit;
