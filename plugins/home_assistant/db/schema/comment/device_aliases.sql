comment on table orac_ha.device_aliases is
  'Persistent operator-maintained aliases for Home Assistant entities.'
;

comment on column orac_ha.device_aliases.alias_name is
  'Canonical lowercase alias text. One alias may address multiple entities.'
;

comment on column orac_ha.device_aliases.entity_id is
  'Home Assistant entity ID retained independently of structural sync rows.'
;
