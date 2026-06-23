declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_HA'
     and constraint_name = 'HA_DEVICES_LABELS_JSON';

  if l_count = 0
  then
    execute immediate q'~
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_ha.ha_devices
  add constraint ha_devices_labels_json
  check (labels is json)
    ~';
  end if;
end;
/
