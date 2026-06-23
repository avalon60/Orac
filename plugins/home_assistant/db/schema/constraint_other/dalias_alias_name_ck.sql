declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'DALIAS_ALIAS_NAME_CK';

  if l_count = 0
  then
    execute immediate q'~
      alter table orac_ha.device_aliases
        add constraint dalias_alias_name_ck
        check (
          alias_name = lower(trim(alias_name))
          and length(trim(alias_name)) > 0
        )
    ~';
  end if;
end;
/
