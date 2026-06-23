declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_ENTITIES_UK1';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_entities
  add constraint ha_entities_uk1
  unique (ha_entity_id)
  using index orac_ha.ha_entities_uk1_idx
    ~';
  end if;
end;
/
