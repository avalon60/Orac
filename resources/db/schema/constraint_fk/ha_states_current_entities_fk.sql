-- __author__: clive bostock
-- __date__: 2025-12-28
-- __description__: generated/synchronised by Cline; one object per file

alter table orac.ha_states_current
  add constraint ha_states_current_entities_fk
  foreign key (entity_id)
  references orac.ha_entities (entity_id);
