declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_indexes
   where owner = 'ORAC_HA'
     and index_name = 'HA_DEVICES_PK_IDX';

  if l_count = 0
  then
    execute immediate q'~
create unique index orac_ha.ha_devices_pk_idx
  on orac_ha.ha_devices
  (
    device_id asc
  )
logging
    ~';
  end if;
end;
/
