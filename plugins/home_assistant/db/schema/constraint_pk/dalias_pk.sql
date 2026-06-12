declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'DALIAS_PK';

  if l_count = 0
  then
    execute immediate q'~
      alter table orac_ha.device_aliases
        add constraint dalias_pk
        primary key (alias_name, entity_id)
        using index orac_ha.dalias_pk_idx
    ~';
  end if;
end;
/
