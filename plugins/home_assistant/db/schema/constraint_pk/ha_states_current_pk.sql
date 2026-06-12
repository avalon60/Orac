declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_STATES_CURRENT_PK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_states_current
  add constraint ha_states_current_pk
  primary key (entity_id)
  using index orac_ha.ha_states_current_pk_idx
    ~';
  end if;
end;
/
