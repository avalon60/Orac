declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'DALIAS_ENABLED_FLAG_CK';

  if l_count = 0
  then
    execute immediate q'~
      alter table orac_ha.device_aliases
        add constraint dalias_enabled_flag_ck
        check (enabled_flag in ('Y', 'N'))
    ~';
  end if;
end;
/
