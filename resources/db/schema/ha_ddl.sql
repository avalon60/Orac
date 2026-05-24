--------------------------------------------------------------------------------
-- ha_areas
--------------------------------------------------------------------------------
create table orac_ha.ha_areas (
  area_id                 varchar2(64 char) not null,
  name                    varchar2(255 char) not null,
  floor_id                varchar2(64 char),
  icon                    varchar2(255 char),
  picture                 varchar2(255 char),
  humidity_entity_id      varchar2(255 char),
  temperature_entity_id   varchar2(255 char),
  aliases                 clob,
  labels                  clob,
  created_at              timestamp with time zone,
  modified_at             timestamp with time zone,
  row_version             number not null,
  created_on              timestamp with time zone not null,
  updated_on              timestamp with time zone not null
);

create unique index orac_ha.ha_areas_pk_idx
  on orac_ha.ha_areas (area_id);

alter table orac_ha.ha_areas
  add constraint ha_areas_pk
  primary key (area_id);

alter table orac_ha.ha_areas
  add constraint ha_areas_aliases_json
  check (aliases is json);

alter table orac_ha.ha_areas
  add constraint ha_areas_labels_json
  check (labels is json);

--------------------------------------------------------------------------------
-- ha_devices
--------------------------------------------------------------------------------
create table orac_ha.ha_devices (
  device_id                   varchar2(64 char) not null,
  name                        varchar2(255 char),
  name_by_user                varchar2(255 char),
  manufacturer                varchar2(255 char),
  model                       varchar2(255 char),
  model_id                    varchar2(255 char),
  area_id                     varchar2(64 char),
  via_device_id               varchar2(64 char),
  hw_version                  varchar2(255 char),
  sw_version                  varchar2(255 char),
  serial_number               varchar2(255 char),
  entry_type                  varchar2(64 char),
  disabled_by                 varchar2(64 char),
  primary_config_entry        varchar2(64 char),
  configuration_url           varchar2(1024 char),
  connections                 clob,
  identifiers                 clob,
  config_entries              clob,
  config_entries_subentries   clob,
  labels                      clob,
  created_at                  timestamp with time zone,
  modified_at                 timestamp with time zone,
  row_version                 number not null,
  created_on                  timestamp with time zone not null,
  updated_on                  timestamp with time zone not null
);

create unique index orac_ha.ha_devices_pk_idx
  on orac_ha.ha_devices (device_id);

create index orac_ha.ha_devices_area_id_idx
  on orac_ha.ha_devices (area_id);

alter table orac_ha.ha_devices
  add constraint ha_devices_pk
  primary key (device_id);

alter table orac_ha.ha_devices
  add constraint ha_devices_connections_json
  check (connections is json);

alter table orac_ha.ha_devices
  add constraint ha_devices_identifiers_json
  check (identifiers is json);

alter table orac_ha.ha_devices
  add constraint ha_devices_config_entries_json
  check (config_entries is json);

alter table orac_ha.ha_devices
  add constraint ha_devices_cfg_subentries_json
  check (config_entries_subentries is json);

alter table orac_ha.ha_devices
  add constraint ha_devices_labels_json
  check (labels is json);

alter table orac_ha.ha_devices
  add constraint ha_devices_areas_fk
  foreign key (area_id)
  references orac_ha.ha_areas (area_id);

--------------------------------------------------------------------------------
-- ha_entities
--------------------------------------------------------------------------------
create table orac_ha.ha_entities (
  entity_id            varchar2(255 char) not null,
  ha_entity_id         varchar2(64 char) not null,
  unique_id            varchar2(255 char),
  platform             varchar2(64 char),
  device_id            varchar2(64 char),
  area_id              varchar2(64 char),
  config_entry_id      varchar2(64 char),
  config_subentry_id   varchar2(64 char),
  entity_category      varchar2(32 char),
  disabled_by          varchar2(32 char),
  hidden_by            varchar2(32 char),
  has_entity_name      varchar2(1 char),
  name                 varchar2(255 char),
  original_name        varchar2(255 char),
  translation_key      varchar2(255 char),
  icon                 varchar2(255 char),
  created_at           timestamp with time zone,
  modified_at          timestamp with time zone,
  options              clob,
  categories           clob,
  labels               clob,
  row_version          number not null,
  created_on           timestamp with time zone not null,
  updated_on           timestamp with time zone not null
);

create unique index orac_ha.ha_entities_pk_idx
  on orac_ha.ha_entities (entity_id);

create unique index orac_ha.ha_entities_uk1_idx
  on orac_ha.ha_entities (ha_entity_id);

create index orac_ha.ha_entities_device_id_idx
  on orac_ha.ha_entities (device_id);

alter table orac_ha.ha_entities
  add constraint ha_entities_pk
  primary key (entity_id);

alter table orac_ha.ha_entities
  add constraint ha_entities_uk1
  unique (ha_entity_id);

alter table orac_ha.ha_entities
  add constraint ha_entities_devices_fk
  foreign key (device_id)
  references orac_ha.ha_devices (device_id);

alter table orac_ha.ha_entities
  add constraint ha_entities_options_json
  check (options is json);

alter table orac_ha.ha_entities
  add constraint ha_entities_categories_json
  check (categories is json);

alter table orac_ha.ha_entities
  add constraint ha_entities_labels_json
  check (labels is json);

--------------------------------------------------------------------------------
-- ha_states_current
--------------------------------------------------------------------------------
create table orac_ha.ha_states_current (
  entity_id           varchar2(255 char) not null,
  state               varchar2(255 char),
  attributes          clob,
  last_changed        timestamp with time zone,
  last_updated        timestamp with time zone,
  last_reported       timestamp with time zone,
  context_id          varchar2(64 char),
  context_parent_id   varchar2(64 char),
  context_user_id     varchar2(64 char),
  row_version         number not null,
  created_on          timestamp with time zone not null,
  updated_on          timestamp with time zone not null
);

create unique index orac_ha.ha_states_current_pk_idx
  on orac_ha.ha_states_current (entity_id);

create index orac_ha.ha_states_current_state_idx
  on orac_ha.ha_states_current (state);

alter table orac_ha.ha_states_current
  add constraint ha_states_current_pk
  primary key (entity_id);

alter table orac_ha.ha_states_current
  add constraint ha_states_current_attributes_json
  check (attributes is json);

alter table orac_ha.ha_states_current
  add constraint ha_states_current_entities_fk
  foreign key (entity_id)
  references orac_ha.ha_entities (entity_id);
