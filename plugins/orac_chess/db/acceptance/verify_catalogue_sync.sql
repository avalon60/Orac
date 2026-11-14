-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Purpose: Verify private catalogue synchronisation with isolated rollback fixtures.
-- Usage: @plugins/orac_chess/db/acceptance/verify_catalogue_sync.sql
-- Requires the explicitly authorised DEV owner session, or SYSTEM with
-- CURRENT_SCHEMA=ORAC_CHESS. Never include this fixture harness in deployment.
whenever sqlerror exit failure rollback
set serveroutput on
set define off

declare
  l_report clob;
  l_payload clob;
  l_before clob;
  l_sequences clob;
  l_transaction varchar2(100);
  l_savepoint boolean := false;
  l_object json_object_t;
  l_entries json_array_t;
  l_detail json_object_t;
  l_fields json_object_t;
  l_sets json_object_t;
  l_result json_object_t;
  l_first_plan json_object_t;
  l_id number;
  l_adopted_id number;
  l_custom_id number;
  l_gambit_id number;
  l_deleted_id number;
  l_dependency_root number;
  l_main_id number;
  l_branch_id number;
  l_version number;
  l_next number;
  l_count number;
  l_text varchar2(4000);
  l_description clob;
  l_original clob;
  l_failed boolean;
  l_protected clob;

  -- BASE_FIXTURE_JSON: independently validated by the Python fixture tests.
  function fixture return clob is
  begin
    return to_clob(q'~{
  "source_revision": "acceptance-v1",
  "entries": [
    {
      "key": "sync_accept_opening",
      "kind": "OPENING",
      "source_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "desired": {
        "fields": {
          "name": "__SYNC_ACCEPT_CREATED",
          "description": "Source initial",
          "opening_type": "OPENING",
          "parent_key": null
        },
        "relationships": {
          "eco_codes": [
            "A00"
          ],
          "aliases": [
            "__SYNC_ACCEPT_SOURCE_ALIAS"
          ]
        }
      }
    },
    {
      "key": "sync_accept_adopted",
      "kind": "OPENING",
      "source_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "desired": {
        "fields": {
          "name": "__SYNC_ACCEPT_ADOPTED",
          "description": "Source must not replace user",
          "opening_type": "OPENING",
          "parent_key": null
        },
        "relationships": {
          "eco_codes": [],
          "aliases": []
        }
      }
    },
    {
      "key": "sync_accept_deleted",
      "kind": "OPENING",
      "source_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "desired": {
        "fields": {
          "name": "__SYNC_ACCEPT_DELETE",
          "description": "Delete fixture",
          "opening_type": "OPENING",
          "parent_key": null
        },
        "relationships": {
          "eco_codes": [],
          "aliases": []
        }
      }
    },
    {
      "key": "sync_accept_gambit",
      "kind": "GAMBIT",
      "source_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "desired": {
        "fields": {
          "name": "__SYNC_ACCEPT_GAMBIT",
          "description": "Source gambit"
        },
        "relationships": {
          "eco_codes": [
            "A00"
          ],
          "opening_keys": [
            "sync_accept_opening"
          ]
        }
      }
    },
    {
      "key": "sync_accept_main",
      "kind": "VARIATION",
      "source_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "desired": {
        "fields": {
          "name": "__SYNC_ACCEPT_MAIN",
          "annotation": "Source main",
          "pgn": "1. e4 *",
          "line_kind": "MAIN",
          "branch_ply": null,
          "starting_fen": null,
          "owner_kind": "OPENING",
          "owner_key": "sync_accept_opening",
          "parent_key": null
        },
        "relationships": {
          "eco_codes": [
            "B00"
          ]
        }
      }
    },
    {
      "key": "sync_accept_branch",
      "kind": "VARIATION",
      "source_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "desired": {
        "fields": {
          "name": "__SYNC_ACCEPT_BRANCH",
          "annotation": "Source branch",
          "pgn": "1. e4 e5 *",
          "line_kind": "CONTINUATION",
          "branch_ply": 1,
          "starting_fen": null,
          "owner_kind": "OPENING",
          "owner_key": "sync_accept_opening",
          "parent_key": "sync_accept_main"
        },
        "relationships": {
          "eco_codes": [
            "C20"
          ]
        }
      }
    }
  ]
}~');
  end;

  procedure refresh_hashes is
    l_entry json_object_t;
    l_desired varchar2(32767);
    l_hash varchar2(64);
  begin
    for i in 0..l_entries.get_size-1 loop
      l_entry := treat(l_entries.get(i) as json_object_t);
      l_desired := l_entry.get_object('desired').to_string;
      select lower(rawtohex(standard_hash(l_desired,'SHA256'))) into l_hash from dual;
      l_entry.put('source_hash',l_hash);
      l_entries.put(i,l_entry,true);
    end loop;
    l_object.put('entries',l_entries);
    l_payload := l_object.to_clob;
  end;

  procedure append_entry(p_entry json_object_t,p_fields json_object_t) is
    l_entry json_object_t := p_entry;
    l_desired json_object_t := p_entry.get_object('desired');
  begin
    l_desired.put('fields',p_fields);
    l_entry.put('desired',l_desired);
    l_entries.append(l_entry);
  end;

  procedure field(p_index number,p_name varchar2,p_value varchar2) is
    l_desired json_object_t;
  begin
    l_detail := treat(l_entries.get(p_index) as json_object_t);
    l_desired := l_detail.get_object('desired');
    l_fields := l_desired.get_object('fields');
    l_fields.put(p_name,p_value);
    l_desired.put('fields',l_fields);
    l_detail.put('desired',l_desired);
    l_entries.put(p_index,l_detail,true);
    refresh_hashes;
  end;

  procedure require(p_ok boolean,p_message varchar2) is
  begin
    if p_ok is null or not p_ok then
      raise_application_error(-20991,p_message);
    end if;
  end;

  function sequence_snapshot return clob is
    l_result clob := to_clob('');
    l_value number;
    l_text varchar2(100);
  begin
    for r in (select sequence_name from all_sequences
              where sequence_owner='ORAC_CHESS' order by sequence_name) loop
      begin
        execute immediate 'select orac_chess."'||r.sequence_name||'".currval from dual' into l_value;
        l_text := to_char(l_value);
      exception when others then
        if sqlcode=-8002 then l_text:='UNINITIALISED'; else raise; end if;
      end;
      l_result := l_result||r.sequence_name||'='||l_text||chr(10);
    end loop;
    return l_result;
  end;

  function protected_snapshot return clob is
    l_result clob;
  begin
    select json_object(
      'videos' value (select json_arrayagg(json_object('id' value video_id,'version' value row_version)
        order by video_id returning clob) from orac_chess.chess_video_v),
      'video_openings' value (select json_arrayagg(json_object('video' value video_id,'opening' value opening_id)
        order by video_id,opening_id returning clob) from orac_chess.chess_video_opening_v),
      'video_gambits' value (select json_arrayagg(json_object('video' value video_id,'gambit' value gambit_id)
        order by video_id,gambit_id returning clob) from orac_chess.chess_video_gambit_v),
      'video_variations' value (select json_arrayagg(json_object('video' value video_id,'variation' value variation_id)
        order by video_id,variation_id returning clob) from orac_chess.chess_video_variation_v),
      'eco' value (select json_arrayagg(eco_code order by eco_code returning clob) from orac_chess.chess_eco_code)
      returning clob) into l_result from dual;
    return l_result;
  end;

  function domain_snapshot return clob is
    l_result clob;
  begin
    select json_object(
      'openings' value (select json_arrayagg(json_object('id' value opening_id,'name' value name,
        'version' value row_version,'type' value opening_type,'description' value description returning clob)
        order by opening_id returning clob) from orac_chess.chess_opening_v),
      'gambits' value (select json_arrayagg(json_object('id' value gambit_id,'name' value name,
        'version' value row_version,'description' value description returning clob)
        order by gambit_id returning clob) from orac_chess.chess_gambit_v),
      'variations' value (select json_arrayagg(json_object('id' value variation_id,'name' value name,
        'version' value row_version,'pgn' value pgn,'annotation' value annotation,
        'parent' value parent_variation_id,'ply' value branch_ply,'kind' value line_kind returning clob)
        order by variation_id returning clob) from orac_chess.chess_variation_v),
      'ledger' value (select json_arrayagg(json_object('key' value catalogue_key,
        'kind' value entity_kind,'opening' value opening_id,'gambit' value gambit_id,
        'variation' value variation_id,'ownership' value ownership,'revision' value source_revision,
        'hash' value rawtohex(last_source_hash),'baseline' value baseline_json returning clob)
        order by catalogue_key returning clob) from orac_chess.chess_catalogue_entry),
      'videos' value (select json_arrayagg(json_object('id' value video_id,'version' value row_version)
        order by video_id returning clob) from orac_chess.chess_video_v),
      'video_openings' value (select json_arrayagg(json_object('video' value video_id,'opening' value opening_id)
        order by video_id,opening_id returning clob) from orac_chess.chess_video_opening_v),
      'video_gambits' value (select json_arrayagg(json_object('video' value video_id,'gambit' value gambit_id)
        order by video_id,gambit_id returning clob) from orac_chess.chess_video_gambit_v),
      'video_variations' value (select json_arrayagg(json_object('video' value video_id,'variation' value variation_id)
        order by video_id,variation_id returning clob) from orac_chess.chess_video_variation_v),
      'eco' value (select json_arrayagg(eco_code order by eco_code returning clob) from orac_chess.chess_eco_code)
      returning clob) into l_result from dual;
    return l_result;
  end;

begin
  require(user in ('ORAC_CHESS','SYSTEM')
    and sys_context('USERENV','CURRENT_SCHEMA')='ORAC_CHESS'
    and sys_context('USERENV','DB_NAME')='FREEPDB1'
    and sys_context('USERENV','CON_NAME')='FREEPDB1',
    'Requires verified authorised DEV ORAC_CHESS owner/current_schema in FREEPDB1/FREEPDB1');
  l_transaction := dbms_transaction.local_transaction_id(false);
  require(l_transaction is null,'Start in a clean session without pending user work');
  l_object := json_object_t.parse(fixture);
  l_entries := l_object.get_array('entries');
  refresh_hashes;
  l_before := domain_snapshot;
  l_protected := protected_snapshot;
  l_sequences := sequence_snapshot;
  orac_chess.chess_catalogue_api.plan_catalogue(l_payload,l_report);
  require(dbms_transaction.local_transaction_id(false) is null,'Dry run started a transaction');
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Dry run changed domain or ledger');
  require(dbms_lob.compare(l_sequences,sequence_snapshot)=0,'Dry run consumed sequence values');
  l_result := json_object_t.parse(l_report);
  require(l_result.get_boolean('dry_run'),'Planner did not identify dry run');
  l_first_plan := l_result.clone;
  savepoint catalogue_sync_acceptance;
  l_savepoint := true;

  select count(*) into l_count from orac_chess.chess_opening_v where name like '__SYNC_ACCEPT_%';
  require(l_count=0,'Acceptance prefix already exists; refusing to touch unrelated data');
  orac_chess.chess_admin_api.save_opening(l_adopted_id,null,'__SYNC_ACCEPT_ADOPTED',
    'SYSTEM',to_clob('User pre-existing description'),null,l_next);
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  l_result := json_object_t.parse(l_report);
  require(l_result.get_number('relationships_added')=l_first_plan.get_number('relationships_added')
    and l_result.get_number('relationships_removed')=l_first_plan.get_number('relationships_removed')
    and l_result.get_number('parent_edges_added')=l_first_plan.get_number('parent_edges_added')
    and l_result.get_number('parent_edges_removed')=l_first_plan.get_number('parent_edges_removed')
    and l_result.get_number('owner_edges_added')=l_first_plan.get_number('owner_edges_added')
    and l_result.get_number('owner_edges_removed')=l_first_plan.get_number('owner_edges_removed'),
    'Fresh apply edge metrics differ from the read-only prediction');
  require(l_result.get_number('parent_edges_added')=1 and l_result.get_number('owner_edges_added')=2,
    'Fresh fixture requires one parent edge and two variation owner edges');
  require(l_result.get_number('validation_failures')=0,'Successful apply reported validation failures');
  select opening_id into l_id from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_opening';
  select variation_id into l_main_id from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_main';
  select variation_id into l_branch_id from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_branch';
  select count(*) into l_count from orac_chess.chess_catalogue_entry
    where catalogue_key like 'sync_accept_%' and ownership='CREATED';
  require(l_count=5,'Fresh fixtures did not create exactly five managed entries');
  select ownership into l_text from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_adopted';
  require(l_text='ADOPTED','Existing untracked row was not protected as ADOPTED');
  select description into l_description from orac_chess.chess_opening_v where opening_id=l_adopted_id;
  require(dbms_lob.compare(l_description,to_clob('User pre-existing description'))=0,'Adoption overwrote existing description');

  l_before := domain_snapshot;
  l_sequences := sequence_snapshot;
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  l_result := json_object_t.parse(l_report);
  require(l_result.get_number('created')=0 and l_result.get_number('updated')=0
    and l_result.get_number('ledger_changes')=0,'Exact repeat reported writes');
  require(l_result.get_number('relationships_added')=0 and l_result.get_number('relationships_removed')=0
    and l_result.get_number('parent_edges_added')=0 and l_result.get_number('parent_edges_removed')=0
    and l_result.get_number('owner_edges_added')=0 and l_result.get_number('owner_edges_removed')=0
    and l_result.get_number('skipped_records')=0 and l_result.get_number('validation_failures')=0,
    'Exact repeat reported relationship, ownership, parent, skip or validation changes');
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Exact repeat changed rows, versions or ledger');
  require(dbms_lob.compare(l_sequences,sequence_snapshot)=0,'Exact repeat consumed sequence values');
  l_object.put('source_revision','acceptance-v2');
  refresh_hashes;
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Version-only source change wrote data or metadata');

  field(0,'description','Source corrected description');
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select description,row_version into l_description,l_version from orac_chess.chess_opening_v where opening_id=l_id;
  require(dbms_lob.compare(l_description,to_clob('Source corrected description'))=0,'Managed source correction was not applied');
  orac_chess.chess_admin_api.save_opening(l_id,l_version,'__SYNC_ACCEPT_CREATED','OPENING',
    to_clob('User description override'),null,l_next);
  -- Identical upstream content must stay entirely read-only after a local edit.
  l_before := domain_snapshot;
  l_sequences := sequence_snapshot;
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  l_result := json_object_t.parse(l_report);
  require(l_result.get_number('updated')=0 and l_result.get_number('ledger_changes')=0,
    'Same source after local edit must not write domain or ledger');
  require(dbms_lob.compare(l_before,domain_snapshot)=0,
    'Same source after local edit changed fields, versions or ledger');
  require(dbms_lob.compare(l_sequences,sequence_snapshot)=0,
    'Same source after local edit consumed sequence values');
  field(0,'description','Another upstream description');
  field(0,'opening_type','SYSTEM');
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select description,opening_type,row_version into l_description,l_text,l_version
    from orac_chess.chess_opening_v where opening_id=l_id;
  require(dbms_lob.compare(l_description,to_clob('User description override'))=0 and l_text='SYSTEM',
    'Field-level merge failed: preserve user description and update independent type');
  l_result := json_object_t.parse(l_report);
  require(l_result.get_array('conflicts').get_size>0,'Conflict was not reported');
  require(l_result.get_number('conflicting_record_count')>0
    and l_result.get_number('conflict_detail_count')=l_result.get_array('conflicts').get_size
    and l_result.get_number('conflicting_record_count')<=l_result.get_number('conflict_detail_count'),
    'Conflict record/detail metrics do not match the structured report');

  orac_chess.chess_admin_api.save_opening(l_id,l_version,'__SYNC_ACCEPT_USER_RENAMED','SYSTEM',
    l_description,null,l_next);
  select row_version into l_version from orac_chess.chess_variation_v where variation_id=l_branch_id;
  orac_chess.chess_variation_api.save_variation(l_branch_id,l_version,l_id,null,l_main_id,1,
    '__SYNC_ACCEPT_BRANCH','CONTINUATION',to_clob('1. e4 c5 *'),null,to_clob('Source branch'),l_next);
  field(5,'annotation','Upstream annotation correction');
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select name into l_text from orac_chess.chess_opening_v where opening_id=l_id;
  require(l_text='__SYNC_ACCEPT_USER_RENAMED','Stable identity did not preserve user rename');
  select pgn,annotation into l_description,l_original from orac_chess.chess_variation_v where variation_id=l_branch_id;
  require(dbms_lob.compare(l_description,to_clob('1. e4 c5 *'))=0
    and dbms_lob.compare(l_original,to_clob('Upstream annotation correction'))=0,
    'Stable variation identity lost user PGN or independent annotation correction');

  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_id;
  orac_chess.chess_admin_api.link_opening_alias(l_id,'__SYNC_ACCEPT_USER_ALIAS',l_version,true,l_next);
  orac_chess.chess_admin_api.link_opening_alias(l_id,'__SYNC_ACCEPT_SOURCE_ALIAS',l_next,false,l_version);
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select count(*) into l_count from orac_chess.chess_opening_alias_v where opening_id=l_id and alias_name='__SYNC_ACCEPT_USER_ALIAS';
  require(l_count=1,'Source sync removed a user-added relationship');
  select count(*) into l_count from orac_chess.chess_opening_alias_v where opening_id=l_id and alias_name='__SYNC_ACCEPT_SOURCE_ALIAS';
  require(l_count=0,'Source sync resurrected a user-removed relationship');

  -- Coordinated source topology changes must not invalidate an installed
  -- subtree while ordinary APIs enforce each intermediate parent-child state.
  l_original := l_payload;
  l_detail := treat(l_entries.get(2) as json_object_t).clone;
  l_detail.put('key','sync_accept_topology_owner');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_TOPOLOGY_OWNER'); l_fields.put_null('parent_key'); append_entry(l_detail,l_fields);
  l_detail := treat(l_entries.get(4) as json_object_t).clone;
  l_detail.put('key','sync_accept_topology_main');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_TOPOLOGY_MAIN'); l_fields.put('owner_key','sync_accept_topology_owner'); append_entry(l_detail,l_fields);
  l_detail := treat(l_entries.get(5) as json_object_t).clone;
  l_detail.put('key','sync_accept_topology_child');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_TOPOLOGY_CHILD'); l_fields.put('owner_key','sync_accept_topology_owner');
  l_fields.put('parent_key','sync_accept_topology_main'); append_entry(l_detail,l_fields);
  refresh_hashes;
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  field(7,'pgn','1. d4 *'); field(8,'pgn','1. d4 d5 *');
  field(7,'annotation','Independent parent annotation correction');
  field(8,'annotation','Independent child annotation correction');
  l_before := domain_snapshot;
  l_sequences := sequence_snapshot;
  orac_chess.chess_catalogue_api.plan_catalogue(l_payload,l_report);
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Topology-conflict dry run changed domain or ledger');
  require(dbms_lob.compare(l_sequences,sequence_snapshot)=0,'Topology-conflict dry run consumed sequences');
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select pgn,annotation into l_description,l_original from orac_chess.chess_variation_v where name='__SYNC_ACCEPT_TOPOLOGY_MAIN';
  require(dbms_lob.compare(l_description,to_clob('1. e4 *'))=0
    and dbms_lob.compare(l_original,to_clob('Independent parent annotation correction'))=0,
    'Parent topology was not retained with its independent annotation correction');
  select pgn,annotation into l_description,l_original from orac_chess.chess_variation_v where name='__SYNC_ACCEPT_TOPOLOGY_CHILD';
  require(dbms_lob.compare(l_description,to_clob('1. e4 e5 *'))=0
    and dbms_lob.compare(l_original,to_clob('Independent child annotation correction'))=0,
    'Child topology was not retained with its independent annotation correction');
  l_result := json_object_t.parse(l_report);
  require(l_result.get_array('conflicts').get_size>0,'Retained subtree topology conflict was not reported');
  -- Unsupported owner changes retain the complete move/topology group,
  -- including a proposed otherwise-legal PGN in the other owner's context.
  declare
    l_before_child orac_chess.chess_variation_v%rowtype;
    l_after_child orac_chess.chess_variation_v%rowtype;
  begin
    select * into l_before_child from orac_chess.chess_variation_v where name='__SYNC_ACCEPT_TOPOLOGY_CHILD';
    field(7,'pgn','1. e4 *');
    field(8,'owner_key','sync_accept_opening'); field(8,'parent_key','sync_accept_main');
    field(8,'pgn','1. e4 c6 *'); field(8,'annotation','Independent annotation beside unsupported owner change');
    orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
    select * into l_after_child from orac_chess.chess_variation_v where variation_id=l_before_child.variation_id;
    require(l_after_child.opening_id=l_before_child.opening_id
      and l_after_child.parent_variation_id=l_before_child.parent_variation_id
      and dbms_lob.compare(l_after_child.pgn,l_before_child.pgn)=0
      and l_after_child.line_kind=l_before_child.line_kind
      and l_after_child.branch_ply=l_before_child.branch_ply
      and nvl(l_after_child.starting_fen,'#')=nvl(l_before_child.starting_fen,'#'),
      'Unsupported owner change modified the retained move/topology group');
    require(dbms_lob.compare(l_after_child.annotation,to_clob('Independent annotation beside unsupported owner change'))=0,
      'Unsupported owner conflict prevented an independent annotation update');
    l_result := json_object_t.parse(l_report);
    require(l_result.get_array('conflicts').get_size>0,'Unsupported owner topology conflict was not reported');
    require(l_result.get_number('owner_edges_added')=0 and l_result.get_number('owner_edges_removed')=0,
      'Rejected owner change reported actual ownership edge writes');
  end;
  -- Remove only temporary source entries from subsequent fixture payloads.
  l_entries.remove(8); l_entries.remove(7); l_entries.remove(6); refresh_hashes;

  -- A user may add links to valid rows wholly outside source ownership.
  orac_chess.chess_admin_api.save_opening(l_custom_id,null,'__SYNC_ACCEPT_CUSTOM',
    'OPENING',to_clob('Untracked custom opening'),null,l_next);
  select gambit_id into l_gambit_id from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_gambit';
  select row_version into l_version from orac_chess.chess_gambit_v where gambit_id=l_gambit_id;
  orac_chess.chess_admin_api.link_gambit_opening(l_gambit_id,l_custom_id,l_version,true,l_next);
  field(3,'description','Upstream gambit correction beside custom user link');
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select count(*) into l_count from orac_chess.chess_opening_gambit_v
    where gambit_id=l_gambit_id and opening_id=l_custom_id;
  require(l_count=1,'Sync lost a user relationship to an untracked custom opening');
  -- The same observed-only reference handling must preserve a custom parent.
  select opening_id into l_deleted_id from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_deleted';
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_deleted_id;
  orac_chess.chess_admin_api.save_opening(l_deleted_id,l_version,'__SYNC_ACCEPT_DELETE',
    'OPENING',to_clob('Delete fixture'),l_custom_id,l_next);
  field(2,'description','Upstream correction beside user parent');
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select parent_opening_id,description into l_next,l_description from orac_chess.chess_opening_v
    where opening_id=l_deleted_id;
  require(l_next=l_custom_id and dbms_lob.compare(l_description,to_clob('Upstream correction beside user parent'))=0,
    'Sync lost an untracked user parent or skipped an independent source correction');

  select opening_id into l_next from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_deleted';
  select row_version into l_version from orac_chess.chess_opening_v where opening_id=l_next;
  orac_chess.chess_admin_api.delete_opening(l_next,l_version);
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select count(*) into l_count from orac_chess.chess_opening_v where name='__SYNC_ACCEPT_DELETE';
  require(l_count=0,'Tombstoned managed entity was resurrected');
  l_result := json_object_t.parse(l_report);
  require(l_result.get_number('tombstones')>0,'Deleted managed identity did not report tombstone');
  -- Known deleted dependencies skip new descendants, not unrelated additions.
  l_original := l_payload;
  l_detail := treat(l_entries.get(4) as json_object_t).clone;
  l_detail.put('key','sync_accept_blocked_owner_main');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_BLOCKED_OWNER_MAIN'); l_fields.put('owner_key','sync_accept_deleted');
  append_entry(l_detail,l_fields);
  l_detail := treat(l_entries.get(5) as json_object_t).clone;
  l_detail.put('key','sync_accept_blocked_owner_child');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_BLOCKED_OWNER_CHILD'); l_fields.put('owner_key','sync_accept_deleted');
  l_fields.put('parent_key','sync_accept_blocked_owner_main'); append_entry(l_detail,l_fields);
  l_detail := treat(l_entries.get(2) as json_object_t).clone;
  l_detail.put('key','sync_accept_unrelated');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_UNRELATED'); l_fields.put_null('parent_key'); append_entry(l_detail,l_fields);
  l_detail := treat(l_entries.get(4) as json_object_t).clone;
  l_detail.put('key','sync_accept_dependency_root');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_DEPENDENCY_ROOT'); l_fields.put('owner_key','sync_accept_unrelated'); append_entry(l_detail,l_fields);
  refresh_hashes;
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select count(*) into l_count from orac_chess.chess_opening_v where name='__SYNC_ACCEPT_UNRELATED';
  require(l_count=1,'Deleted owner dependency prevented unrelated creation');
  select count(*) into l_count from orac_chess.chess_variation_v where name in ('__SYNC_ACCEPT_BLOCKED_OWNER_MAIN','__SYNC_ACCEPT_BLOCKED_OWNER_CHILD');
  require(l_count=0,'Deleted owner or blocked ancestor was resurrected through a descendant');
  l_result := json_object_t.parse(l_report);
  require(l_result.get_array('conflicts').get_size>=2,'Deleted owner dependency conflicts not reported');
  select variation_id into l_dependency_root from orac_chess.chess_catalogue_entry where catalogue_key='sync_accept_dependency_root';
  -- Direct ECO links legitimately restrict deletion; remove them through the
  -- complete public save operation using the currently observed row version.
  declare
    l_root orac_chess.chess_variation_v%rowtype;
  begin
    select * into l_root from orac_chess.chess_variation_v where variation_id=l_dependency_root;
    orac_chess.chess_variation_api.save_variation_with_eco(
      l_dependency_root,l_root.row_version,l_root.opening_id,l_root.gambit_id,
      l_root.parent_variation_id,l_root.branch_ply,l_root.name,l_root.line_kind,
      l_root.pgn,l_root.starting_fen,l_root.annotation,null,l_next);
    orac_chess.chess_variation_api.delete_variation(l_dependency_root,l_next);
  end;
  l_detail := treat(l_entries.get(5) as json_object_t).clone;
  l_detail.put('key','sync_accept_blocked_parent_child');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_BLOCKED_PARENT_CHILD'); l_fields.put('owner_key','sync_accept_unrelated');
  l_fields.put('parent_key','sync_accept_dependency_root'); append_entry(l_detail,l_fields);
  l_detail := treat(l_entries.get(5) as json_object_t).clone;
  l_detail.put('key','sync_accept_blocked_parent_grandchild');
  l_fields := l_detail.get_object('desired').get_object('fields');
  l_fields.put('name','__SYNC_ACCEPT_BLOCKED_PARENT_GRANDCHILD'); l_fields.put('owner_key','sync_accept_unrelated');
  l_fields.put('parent_key','sync_accept_blocked_parent_child'); l_fields.put('pgn','1. e4 e5 2. Nf3 *');
  l_fields.put('branch_ply',2); append_entry(l_detail,l_fields);
  l_detail := treat(l_entries.get(3) as json_object_t);
  l_sets := l_detail.get_object('desired').get_object('relationships');
  declare
    l_keys json_array_t := l_sets.get_array('opening_keys');
    l_desired json_object_t := l_detail.get_object('desired');
  begin
    l_keys.append('sync_accept_deleted'); l_sets.put('opening_keys',l_keys);
    l_desired.put('relationships',l_sets); l_detail.put('desired',l_desired);
    l_entries.put(3,l_detail,true);
  end;
  refresh_hashes;
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select count(*) into l_count from orac_chess.chess_variation_v where name in ('__SYNC_ACCEPT_DEPENDENCY_ROOT','__SYNC_ACCEPT_BLOCKED_PARENT_CHILD','__SYNC_ACCEPT_BLOCKED_PARENT_GRANDCHILD');
  require(l_count=0,'Deleted parent or blocked descendant was recreated');
  l_result := json_object_t.parse(l_report);
  require(l_result.get_array('conflicts').get_size>=4,'Deleted parent/dependent chain conflicts not reported');
  l_object := json_object_t.parse(l_original); l_entries := l_object.get_array('entries'); refresh_hashes;
  l_original := l_payload;
  l_entries.remove(3);
  refresh_hashes;
  orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  select count(*) into l_count from orac_chess.chess_gambit_v where name='__SYNC_ACCEPT_GAMBIT';
  require(l_count=1,'Upstream omission deleted an existing entity');
  l_result := json_object_t.parse(l_report);
  require(instr(l_result.get_array('deprecated').to_string,'sync_accept_gambit')>0,'Upstream omission not reported as deprecated');

  l_object := json_object_t.parse(l_original); l_entries:=l_object.get_array('entries'); refresh_hashes;
  -- Invalid final entry must roll back earlier planned valid changes.
  field(0,'opening_type','OPENING');
  l_detail := treat(l_entries.get(5) as json_object_t); l_detail.put('key','sync_accept_invalid'); l_entries.put(5,l_detail,true);
  field(5,'name','__SYNC_ACCEPT_INVALID'); field(5,'pgn','1. e4 e5 2. Ke3 *');
  l_before := domain_snapshot; l_failed:=false;
  l_sequences := sequence_snapshot;
  begin orac_chess.chess_catalogue_api.plan_catalogue(l_payload,l_report);
  exception when others then l_failed:=true; end;
  require(l_failed,'Invalid payload unexpectedly accepted by read-only planner');
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Invalid dry run changed data or ledger');
  require(dbms_lob.compare(l_sequences,sequence_snapshot)=0,'Invalid dry run consumed sequence values');
  l_failed:=false;
  begin orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  exception when others then l_failed:=true; end;
  require(l_failed,'Illegal late PGN unexpectedly succeeded');
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Late invalid PGN left partial domain/ledger writes');
  l_object := json_object_t.parse(l_original); l_entries:=l_object.get_array('entries');
  l_detail := treat(l_entries.get(5) as json_object_t); l_detail.put('key','sync_accept_missing'); l_entries.put(5,l_detail,true);
  field(5,'name','__SYNC_ACCEPT_MISSING'); field(5,'owner_key','sync_accept_missing_owner');
  l_before := domain_snapshot; l_failed:=false;
  l_sequences := sequence_snapshot;
  begin orac_chess.chess_catalogue_api.plan_catalogue(l_payload,l_report);
  exception when others then l_failed:=true; end;
  require(l_failed,'Invalid payload unexpectedly accepted by read-only planner');
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Invalid dry run changed data or ledger');
  require(dbms_lob.compare(l_sequences,sequence_snapshot)=0,'Invalid dry run consumed sequence values');
  l_failed:=false;
  begin orac_chess.chess_catalogue_api.apply_catalogue(l_payload,l_report);
  exception when others then l_failed:=true; end;
  require(l_failed,'Missing owner unexpectedly succeeded');
  require(dbms_lob.compare(l_before,domain_snapshot)=0,'Missing owner left partial domain/ledger writes');

  require(dbms_lob.compare(l_protected,protected_snapshot)=0,'Catalogue sync changed video versions or central ECO reference');
  rollback to catalogue_sync_acceptance;
  rollback;
  l_savepoint:=false;
  dbms_output.put_line('PASS: dry run, managed creation/repeat/correction, user overrides, adoption, tombstone, deprecation, relationship overrides and atomic failures');
exception
  when others then
    if l_savepoint then rollback to catalogue_sync_acceptance; end if;
    raise;
end;
/
