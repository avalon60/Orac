create table plugins_core.ha_entities
(
  entity_id          varchar2(255 char) not null,
  ha_entity_id       varchar2(64 char) not null,
  unique_id          varchar2(255 char),
  platform           varchar2(64 char),
  device_id          varchar2(64 char),
  area_id            varchar2(64 char),
  config_entry_id    varchar2(64 char),
  config_subentry_id varchar2(64 char),
  entity_category    varchar2(32 char),
  disabled_by        varchar2(32 char),
  hidden_by          varchar2(32 char),
  has_entity_name    varchar2(1 char),
  name               varchar2(255 char),
  original_name      varchar2(255 char),
  translation_key    varchar2(255 char),
  icon               varchar2(255 char),
  created_at         timestamp with time zone,
  modified_at        timestamp with time zone,
  options            clob,
  categories         clob,
  labels             clob,
  row_version        number not null,
  created_on         timestamp with time zone not null,
  updated_on         timestamp with time zone not null
)
logging
no inmemory
lob (options) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
lob (categories) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
lob (labels) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
;
