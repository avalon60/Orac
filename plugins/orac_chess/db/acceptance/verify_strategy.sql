-- Author: Clive Bostock
-- Date: 12-Nov-2026
-- Purpose: Exercise strategy compatibility and three-way merge through installed APIs.
-- Usage: sql /nolog; conn -name orac-db; @plugins/orac_chess/db/acceptance/verify_strategy.sql
whenever sqlerror exit failure rollback
set serveroutput on
set define off

declare
  l_id number;
  l_version number;
  l_next number;
  l_report clob;
  l_payload clob;
  l_text clob;
  l_name varchar2(200):='Strategy acceptance '||rawtohex(sys_guid());
  l_key varchar2(100):='strategy_acceptance_'||lower(rawtohex(sys_guid()));
  procedure require(p_ok boolean,p_message varchar2) is
  begin if not p_ok or p_ok is null then raise_application_error(-20090,p_message); end if; end;
  procedure apply(p_strategy varchar2,p_revision varchar2,p_include boolean default true) is
    l_hash varchar2(64);
    l_fields json_object_t:=json_object_t();
    l_sets json_object_t:=json_object_t();
    l_entry json_object_t:=json_object_t();
    l_desired json_object_t:=json_object_t();
    l_entries json_array_t:=json_array_t();
    l_root json_object_t:=json_object_t();
  begin
    l_fields.put('name',l_name); l_fields.put('description','Acceptance description');
    l_fields.put('opening_type','OPENING'); l_fields.put_null('parent_key');
    if p_include then l_fields.put('strategy',p_strategy); end if;
    l_sets.put('eco_codes',json_array_t()); l_sets.put('aliases',json_array_t());
    l_desired.put('fields',l_fields);l_desired.put('relationships',l_sets);
    l_entry.put('key',l_key);l_entry.put('kind','OPENING');
    select lower(rawtohex(standard_hash(p_revision,'SHA256'))) into l_hash from dual;
    l_entry.put('source_hash',l_hash);
    l_entry.put('desired',l_desired);l_entries.append(l_entry);
    l_root.put('source_revision',p_revision);l_root.put('entries',l_entries);
    l_payload:=l_root.to_clob;
    orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  end;
  procedure check_strategy(p_expected varchar2,p_message varchar2) is
  begin
    select strategy,row_version into l_text,l_version from orac_chess.chess_opening_v where opening_id=l_id;
    require((l_text is null and p_expected is null) or dbms_lob.compare(l_text,to_clob(p_expected))=0,p_message);
  end;
begin
  savepoint strategy_acceptance;
  -- Adopted blank rows allow only first strategy initialisation.
  orac_chess.chess_admin_api.save_opening(l_id,null,l_name,'OPENING','Acceptance description',null,l_version);
  apply('Initial strategy','strategy-acceptance-1');
  check_strategy('Initial strategy','Blank adopted strategy was not initialised');
  -- Legacy writer preserves strategy, including the ECO overload.
  orac_chess.chess_admin_api.save_opening(l_id,l_version,l_name,'OPENING','Acceptance description',null,l_next);
  check_strategy('Initial strategy','Legacy opening writer erased strategy');
  orac_chess.chess_admin_api.save_opening_with_eco(l_id,l_version,l_name,'OPENING','Acceptance description',null,null,l_next);
  check_strategy('Initial strategy','Legacy ECO writer erased strategy');
  apply('Upstream plan.'||chr(10)||chr(10)||'Supporting position.','strategy-acceptance-2');
  check_strategy('Upstream plan.'||chr(10)||chr(10)||'Supporting position.','Multiline source strategy did not follow upstream');
  apply('Upstream plan.'||chr(10)||chr(10)||'Supporting position.','strategy-acceptance-2');
  check_strategy('Upstream plan.'||chr(10)||chr(10)||'Supporting position.','Multiline source rerun changed paragraphs');
  -- Explicit clear is a local override, including after repeated sync.
  orac_chess.chess_admin_api.save_opening(l_id,l_version,l_name,'OPENING','Acceptance description',to_clob(null),null,l_next);
  check_strategy(null,'Explicit null did not clear');
  apply('Later source','strategy-acceptance-3');
  check_strategy(null,'Source reseeded an explicit clear');
  apply('Later source','strategy-acceptance-3');
  check_strategy(null,'Same-source rerun reseeded an explicit clear');
  apply(null,'strategy-acceptance-4',false);
  check_strategy(null,'Missing field changed cleared strategy');
  -- Optimistic locking remains enforced by the new overload.
  begin
    orac_chess.chess_admin_api.save_opening(l_id,-1,l_name,'OPENING','Acceptance description','Bad stale write',null,l_next);
    raise_application_error(-20090,'Stale write unexpectedly succeeded');
  exception when others then if sqlcode!=-20001 then raise; end if; end;
  check_strategy(null,'Stale write altered strategy');
  -- Created rows follow source changes, including explicit source null, until edited.
  l_name:='Strategy created '||rawtohex(sys_guid());
  l_key:='strategy_created_'||lower(rawtohex(sys_guid())); l_id:=null;
  apply('Created strategy','strategy-created-1');
  select opening_id into l_id from orac_chess.chess_opening_v where name=l_name;
  check_strategy('Created strategy','Created strategy missing');
  apply(null,'strategy-created-2');
  check_strategy(null,'Explicit source null did not clear unedited strategy');
  apply('Next strategy','strategy-created-3');
  check_strategy('Next strategy','Created blank source strategy did not follow upstream');
  orac_chess.chess_admin_api.save_opening(l_id,l_version,l_name,'OPENING','Acceptance description','Local plan.'||chr(10)||chr(10)||'Local supporting position.',null,l_next);
  apply('Source after edit','strategy-created-4');
  check_strategy('Local plan.'||chr(10)||chr(10)||'Local supporting position.','Local strategy edit was overwritten');
  apply(null,'strategy-created-5',false);
  check_strategy('Local plan.'||chr(10)||chr(10)||'Local supporting position.','Missing source strategy erased local edit');
  orac_chess.chess_admin_api.delete_opening(l_id,l_version);
  apply('Never recreate','strategy-created-6');
  declare l_count number;
  begin
    select count(*) into l_count from orac_chess.chess_opening_v where name=l_name;
    require(l_count=0,'Deleted tracked identity was recreated');
  end;
  -- Both gambit overload families retain the same preservation/clearing contract.
  declare l_gambit number; l_gversion number; l_gnext number; l_value clob; l_flag varchar2(1); l_length number;
  begin
    orac_chess.chess_admin_api.save_gambit(l_gambit,null,l_name,'Gambit description','Gambit strategy',l_gversion);
    orac_chess.chess_admin_api.save_gambit(l_gambit,l_gversion,l_name,'Gambit description',l_gnext);
    select strategy into l_value from orac_chess.chess_gambit_v where gambit_id=l_gambit;
    require(dbms_lob.compare(l_value,to_clob('Gambit strategy'))=0,'Legacy gambit erased strategy');
    orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,l_gnext,l_name,'Gambit description',null,l_gversion);
    select strategy into l_value from orac_chess.chess_gambit_v where gambit_id=l_gambit;
    require(dbms_lob.compare(l_value,to_clob('Gambit strategy'))=0,'Legacy gambit ECO erased strategy');
    orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,l_gversion,l_name,'Gambit description',to_clob(null),null,l_gnext);
    select strategy into l_value from orac_chess.chess_gambit_v where gambit_id=l_gambit;
    require(l_value is null,'Explicit gambit ECO null did not clear');
    orac_chess.chess_admin_api.save_gambit(l_gambit,l_gnext,l_name,'Gambit description',to_clob(rpad('x',4000,'x')),l_gversion);
    select length(strategy),strategy_truncated into l_length,l_flag
    from orac_chess.chess_query_gambit_text_v where gambit_id=l_gambit;
    require(l_length=2000 and l_flag='Y','Bounded strategy query projection/truncation differs');
  end;
  -- A later invalid entry must roll back an earlier valid insert in the same batch.
  l_name:='Strategy atomic '||rawtohex(sys_guid());
  l_key:='strategy_atomic_'||lower(rawtohex(sys_guid()));
  declare
    l_root json_object_t:=json_object_t.parse(l_payload);
    l_entries json_array_t:=l_root.get_array('entries');
    l_first json_object_t:=treat(l_entries.get(0) as json_object_t);
    l_fields json_object_t:=l_first.get_object('desired').get_object('fields');
    l_bad json_object_t;
    l_count number;
  begin
    l_fields.put('name',l_name);
    declare l_desired json_object_t:=l_first.get_object('desired');
    begin l_desired.put('fields',l_fields); l_first.put('desired',l_desired); end;
    l_first.put('key',l_key); l_entries:=json_array_t(); l_entries.append(l_first);
    l_bad:=treat(l_first.clone as json_object_t); l_bad.put('key',l_key||'_bad'); l_bad.put('kind','INVALID');
    l_entries.append(l_bad);l_root.put('entries',l_entries);
    begin
      orac_chess.chess_catalogue_api.apply_catalogue(l_root.to_clob,l_report);
      raise_application_error(-20090,'Invalid catalogue batch unexpectedly succeeded');
    exception when others then if sqlcode!=-20014 then raise; end if; end;
    select count(*) into l_count from orac_chess.chess_opening_v where name=l_name;
    require(l_count=0,'Failed catalogue batch left a partial insert');
  end;
  rollback to strategy_acceptance;
  dbms_output.put_line('PASS: adopted initialisation, legacy preservation, upstream merge, explicit clear, missing field, rerun, stale lock, created/source null/local edit, tombstone, gambit overloads and atomicity.');
exception when others then
  rollback;
  raise;
end;
/
rollback;
