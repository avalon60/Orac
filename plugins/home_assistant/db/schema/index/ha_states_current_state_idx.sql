declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_indexes
   where owner = 'ORAC_HA'
     and index_name = 'HA_STATES_CURRENT_STATE_IDX';

  if l_count = 0
  then
    execute immediate q'~
create index orac_ha.ha_states_current_state_idx
  on orac_ha.ha_states_current
  (
    state asc
  )
logging
    ~';
  end if;
end;
/
