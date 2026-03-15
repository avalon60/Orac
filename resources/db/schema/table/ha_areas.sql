-- __author__: clive bostock
-- __date__: 2025-12-28
-- __description__: generated/synchronised by Cline; one object per file

create table orac.ha_areas (
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
