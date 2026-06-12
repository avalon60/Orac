declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_tables
   where owner = 'ORAC_HA'
     and table_name = 'HA_STATES_CURRENT';

  if l_count = 0
  then
    execute immediate q'~
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create table orac_ha.ha_states_current
(
  entity_id         varchar2(255 char) not null,
  state             varchar2(255 char),
  attributes        clob,
  last_changed      timestamp with time zone,
  last_updated      timestamp with time zone,
  last_reported     timestamp with time zone,
  context_id        varchar2(64 char),
  context_parent_id varchar2(64 char),
  context_user_id   varchar2(64 char),
  row_version       number not null,
  created_on        timestamp with time zone not null,
  updated_on        timestamp with time zone not null
)
logging
no inmemory
lob (attributes) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
    ~';
  end if;
end;
/
