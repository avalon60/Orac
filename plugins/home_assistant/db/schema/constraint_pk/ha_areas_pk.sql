declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_AREAS_PK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_ha.ha_areas
  add constraint ha_areas_pk
  primary key (area_id)
  using index orac_ha.ha_areas_pk_idx
    ~';
  end if;
end;
/
