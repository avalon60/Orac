-- Author: Clive Bostock
-- Date: 01-Nov-2026
-- Purpose: Report hierarchy defects and authoritative export metadata without modifying data.
-- Usage: In an approved metadata-capable target session, run @plugins/orac_chess/db/acceptance/diagnose_hierarchies.sql
whenever sqlerror exit failure rollback

-- Walk upward from every node, including disconnected cyclic components.
select distinct origin_id as opening_id, 'CYCLE' as problem
from (
  select connect_by_root opening_id as origin_id, connect_by_iscycle as is_cycle
  from orac_chess.chess_opening
  connect by nocycle prior parent_opening_id = opening_id
)
where is_cycle = 1;

select origin_id as variation_id, 'NO_REACHABLE_ROOT' as problem
from (
  select connect_by_root variation_id as origin_id, parent_variation_id
  from orac_chess.chess_variation
  connect by nocycle prior parent_variation_id = variation_id
)
group by origin_id
having max(case when parent_variation_id is null then 1 else 0 end) = 0;

select distinct origin_id as variation_id, 'CYCLE' as problem
from (
  select connect_by_root variation_id as origin_id, connect_by_iscycle as is_cycle
  from orac_chess.chess_variation
  connect by nocycle prior parent_variation_id = variation_id
)
where is_cycle = 1;

select banner_full from v$version;
select owner, table_name, column_name, data_type, data_length, data_precision, data_scale
from all_tab_columns
where owner = 'ORAC_CHESS'
  and table_name = 'DATABASECHANGELOGLOCK' and column_name = 'LOCKED';

-- Identify the database and PDB before interpreting the following metadata.
select sys_context('userenv', 'session_user') as session_user,
  sys_context('userenv', 'db_name') as db_name,
  sys_context('userenv', 'con_name') as con_name,
  sys_context('userenv', 'con_id') as con_id
from dual;
select dbid, name, db_unique_name from v$database;
select con_id, name, dbid, con_uid, rawtohex(guid) as pdb_guid
from v$pdbs where con_id = to_number(sys_context('userenv', 'con_id'));
select name, value from v$parameter
where name in ('max_string_size', 'db_securefile') order by name;

-- Join physical LOB storage to logical column types; extended VARCHAR2 can
-- have LOB backing without being a logical CLOB. Preserve columns without LOBs.
select c.owner, c.table_name, c.column_id, c.column_name, c.data_type,
  c.data_length, c.char_length, c.char_used, c.nullable,
  l.segment_name, l.index_name, l.tablespace_name, l.securefile,
  l.in_row, l.chunk, l.cache, l.logging
from all_tab_columns c
left join all_lobs l on l.owner = c.owner
  and l.table_name = c.table_name and l.column_name = c.column_name
where c.owner = 'ORAC_CHESS'
  and c.table_name in ('CHESS_VARIATION', 'CHESS_GAME', 'CHESS_VIDEO')
order by c.table_name, c.column_id;
