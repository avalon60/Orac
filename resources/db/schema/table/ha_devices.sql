-- __author__: clive bostock
-- __date__: 2025-12-28
-- __description__: generated/synchronised by Cline; one object per file

create table orac.ha_devices (
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
