declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_SYNC_RUNS_TYPE_CK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_sync_runs
  add constraint ha_sync_runs_type_ck
  check (sync_type in ('structural', 'state'))
    ~';
  end if;
end;
/
