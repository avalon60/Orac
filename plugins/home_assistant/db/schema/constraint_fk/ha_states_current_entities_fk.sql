declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_STATES_CURRENT_ENTITIES_FK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_states_current
  add constraint ha_states_current_entities_fk
  foreign key
  (
    entity_id
  )
  references orac_ha.ha_entities
  (
    entity_id
  )
  not deferrable
    ~';
  end if;
end;
/
