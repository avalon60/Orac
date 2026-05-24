alter table orac_ha.ha_entities
  add constraint ha_entities_pk
  primary key (entity_id)
  using index orac_ha.ha_entities_pk_idx
;
