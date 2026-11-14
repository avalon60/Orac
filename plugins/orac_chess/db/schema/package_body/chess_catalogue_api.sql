--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Shared read-only planner and atomic source-managed catalogue synchronisation.
-- Purpose: Three-way merge CREATED records and protect ADOPTED records and tombstones.
-- Usage: Owner-only CHESS_CATALOGUE_API; no public parsing-schema grants.
--changeset clive:orac_chess_catalogue_api_body context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package body orac_chess.chess_catalogue_api as
  function equal_json(p_left json_element_t,p_right json_element_t) return boolean is
    l_left clob;
    l_right clob;
    l_equal number;
    l_left_wrapper json_object_t := json_object_t();
    l_right_wrapper json_object_t := json_object_t();
  begin
    if p_left is null or p_right is null then return p_left is null and p_right is null; end if;
    -- SQL JSON_EQUAL expects object/array documents; wrap scalar strings and nulls.
    l_left_wrapper.put('value',p_left); l_right_wrapper.put('value',p_right);
    l_left := l_left_wrapper.to_clob; l_right := l_right_wrapper.to_clob;
    select case when json_equal(l_left,l_right) then 1 else 0 end into l_equal from dual;
    return l_equal=1;
  end;

  function has_value(p_array json_array_t,p_value varchar2) return boolean is
  begin
    for i in 0..p_array.get_size-1 loop
      if p_array.get_string(i)=p_value then return true; end if;
    end loop;
    return false;
  end;

  function sorted_values(p_values json_array_t) return json_array_t is
    l_values sys.odcivarchar2list := sys.odcivarchar2list();
    l_result json_array_t := json_array_t();
  begin
    for i in 0..p_values.get_size-1 loop l_values.extend; l_values(l_values.count):=p_values.get_string(i); end loop;
    for value in (select distinct column_value from table(l_values) order by column_value) loop l_result.append(value.column_value); end loop;
    return l_result;
  end;

  function selection(p_array json_array_t) return varchar2 is
    l_text varchar2(32767);
  begin
    for i in 0..p_array.get_size-1 loop
      if i>0 then l_text:=l_text||':'; end if;
      l_text:=l_text||p_array.get_string(i);
    end loop;
    return l_text;
  end;

  procedure synchronise(p_payload clob,p_apply boolean,p_report out clob) is
    l_payload json_object_t := json_object_t.parse(p_payload);
    l_entries json_array_t := l_payload.get_array('entries');
    l_revision varchar2(100) := l_payload.get_string('source_revision');
    type id_map is table of number index by varchar2(200);
    type key_map is table of varchar2(100) index by varchar2(100);
    type bool_map is table of boolean index by varchar2(100);
    type ledger_row is record (entity_kind varchar2(12),entity_id number,ownership varchar2(7),source_hash raw(32),baseline clob);
    type pending_map is table of ledger_row index by varchar2(100);
    l_ids id_map;
    l_kinds key_map;
    l_reverse key_map;
    l_seen bool_map;
    l_conflicted_keys bool_map;
    l_pending pending_map;
    type state_map is table of json_object_t index by varchar2(100);
    l_states state_map;
    l_blocked bool_map;
    l_frozen_topology bool_map;
    l_old orac_chess.chess_catalogue_entry%rowtype;
    l_item json_object_t;
    l_desired json_object_t;
    l_source json_object_t;
    l_current json_object_t;
    l_merged json_object_t;
    l_baseline json_object_t;
    l_applied json_object_t;
    l_overrides json_object_t;
    l_snapshot json_object_t;
    l_report json_object_t := json_object_t();
    l_conflicts json_array_t := json_array_t();
    l_deprecated json_array_t := json_array_t();
    l_key varchar2(100);
    l_kind varchar2(12);
    l_ownership varchar2(7);
    l_hash raw(32);
    l_id number;
    l_version number;
    l_next number;
    l_count number;
    l_created number := 0;
    l_updated number := 0;
    l_adopted number := 0;
    l_unchanged number := 0;
    l_tombstones number := 0;
    l_virtual number := -1;
    l_has_old boolean;
    l_old_module varchar2(64);
    l_old_action varchar2(64);
    l_application_info_set boolean := false;
    l_skipped number := 0;
    l_relationships_added number := 0;
    l_relationships_removed number := 0;
    l_parent_edges_added number := 0;
    l_parent_edges_removed number := 0;
    l_owner_edges_added number := 0;
    l_owner_edges_removed number := 0;
    l_metadata_changed boolean;

    function reverse_key(p_kind varchar2,p_id number) return varchar2 is
      l_result varchar2(100);
      l_lookup varchar2(100) := p_kind||':'||to_char(p_id);
    begin
      if p_id is null then return null; end if;
      if l_reverse.exists(l_lookup) then return l_reverse(l_lookup); end if;
      begin
        select catalogue_key into l_result from orac_chess.chess_catalogue_entry
        where (p_kind='OPENING' and opening_id=p_id) or (p_kind='GAMBIT' and gambit_id=p_id)
          or (p_kind='VARIATION' and variation_id=p_id);
        return l_result;
      exception when no_data_found then return '#'||to_char(p_id); end;
    end;

    function resolve_key(p_key varchar2,p_kind varchar2 default null) return number is
      l_result number;
      l_actual_kind varchar2(12);
      l_count number;
    begin
      if p_key is null then return null; end if;
      if regexp_like(p_key,'^#[0-9]+$') and p_kind is not null then
        -- Only snapshots emit opaque references for user-owned, untracked relationships.
        l_result:=to_number(substr(p_key,2));
        if p_kind='OPENING' then select count(*) into l_count from orac_chess.chess_opening_v where opening_id=l_result;
        elsif p_kind='GAMBIT' then select count(*) into l_count from orac_chess.chess_gambit_v where gambit_id=l_result;
        else select count(*) into l_count from orac_chess.chess_variation_v where variation_id=l_result; end if;
        if l_count!=1 then raise_application_error(-20013,'Missing preserved user relationship'); end if;
        return l_result;
      end if;
      if l_ids.exists(p_key) then
        if p_kind is not null and l_kinds(p_key)!=p_kind then raise_application_error(-20022,'Catalogue dependency has wrong entity kind'); end if;
        return l_ids(p_key);
      end if;
      select coalesce(opening_id,gambit_id,variation_id),entity_kind into l_result,l_actual_kind
      from orac_chess.chess_catalogue_entry where catalogue_key=p_key;
      if p_kind is not null and l_actual_kind!=p_kind then raise_application_error(-20022,'Catalogue dependency has wrong entity kind'); end if;
      if l_result is null then raise_application_error(-20013,'Deleted catalogue dependency: '||p_key); end if;
      return l_result;
    exception when no_data_found then raise_application_error(-20013,'Unknown catalogue dependency: '||p_key);
    end;

    function deleted_dependency(p_key varchar2) return boolean is
      l_id number;
    begin
      if p_key is null then return false; end if;
      if l_blocked.exists(p_key) then return true; end if;
      if l_ids.exists(p_key) then return false; end if;
      begin
        select coalesce(opening_id,gambit_id,variation_id) into l_id
        from orac_chess.chess_catalogue_entry where catalogue_key=p_key;
        return l_id is null;
      exception when no_data_found then return false; end;
    end;

    procedure conflict(p_field varchar2,p_reason varchar2) is
      l_detail json_object_t := json_object_t();
    begin
      if l_key is not null then l_conflicted_keys(l_key):=true; end if;
      l_detail.put('key',l_key); l_detail.put('field',p_field); l_detail.put('reason',p_reason);
      l_conflicts.append(l_detail);
    end;

    function snapshot(p_kind varchar2,p_id number,p_version out number) return json_object_t is
      l_fields json_object_t := json_object_t();
      l_sets json_object_t := json_object_t();
      l_result json_object_t := json_object_t();
      l_values json_array_t;
      l_opening orac_chess.chess_opening_v%rowtype;
      l_gambit orac_chess.chess_gambit_v%rowtype;
      l_variation orac_chess.chess_variation_v%rowtype;
    begin
      if p_kind='OPENING' then
        select opening_id,name,opening_type,description,strategy,parent_opening_id,row_version into l_opening
        from orac_chess.chess_opening_v where opening_id=p_id;
        p_version:=l_opening.row_version;
        l_fields.put('name',l_opening.name); l_fields.put('description',l_opening.description); l_fields.put('strategy',l_opening.strategy);
        l_fields.put('opening_type',l_opening.opening_type);
        l_fields.put('parent_key',reverse_key('OPENING',l_opening.parent_opening_id));
        l_values:=json_array_t();
        for e in (select eco_code value from orac_chess.chess_opening_eco_v where opening_id=p_id order by eco_code) loop l_values.append(e.value); end loop;
        l_sets.put('eco_codes',sorted_values(l_values)); l_values:=json_array_t();
        for e in (select alias_name value from orac_chess.chess_opening_alias_v where opening_id=p_id order by alias_name) loop l_values.append(e.value); end loop;
        l_sets.put('aliases',sorted_values(l_values));
      elsif p_kind='GAMBIT' then
        select gambit_id,name,description,strategy,row_version into l_gambit from orac_chess.chess_gambit_v where gambit_id=p_id;
        p_version:=l_gambit.row_version;
        l_fields.put('name',l_gambit.name); l_fields.put('description',l_gambit.description); l_fields.put('strategy',l_gambit.strategy);
        l_values:=json_array_t();
        for e in (select eco_code value from orac_chess.chess_gambit_eco_v where gambit_id=p_id order by eco_code) loop l_values.append(e.value); end loop;
        l_sets.put('eco_codes',sorted_values(l_values)); l_values:=json_array_t();
        for e in (select opening_id from orac_chess.chess_opening_gambit_v where gambit_id=p_id order by opening_id) loop l_values.append(reverse_key('OPENING',e.opening_id)); end loop;
        l_sets.put('opening_keys',sorted_values(l_values));
      else
        select variation_id,opening_id,gambit_id,variation_type,parent_variation_id,branch_ply,name,line_kind,pgn,starting_fen,annotation,row_version
        into l_variation from orac_chess.chess_variation_v where variation_id=p_id;
        p_version:=l_variation.row_version;
        l_fields.put('name',l_variation.name); l_fields.put('annotation',l_variation.annotation);
        l_fields.put('pgn',l_variation.pgn); l_fields.put('line_kind',l_variation.line_kind);
        l_fields.put('branch_ply',l_variation.branch_ply); l_fields.put('starting_fen',l_variation.starting_fen);
        l_fields.put('owner_kind',case when l_variation.opening_id is not null then 'OPENING' else 'GAMBIT' end);
        l_fields.put('owner_key',case when l_variation.opening_id is not null then reverse_key('OPENING',l_variation.opening_id) else reverse_key('GAMBIT',l_variation.gambit_id) end);
        l_fields.put('parent_key',reverse_key('VARIATION',l_variation.parent_variation_id));
        l_values:=json_array_t();
        for e in (select eco_code value from orac_chess.chess_variation_eco_v where variation_id=p_id order by eco_code) loop l_values.append(e.value); end loop;
        l_sets.put('eco_codes',sorted_values(l_values));
      end if;
      l_result.put('fields',l_fields); l_result.put('relationships',l_sets);
      return l_result;
    end;

    function merge_set(p_name varchar2,p_source json_array_t,p_current json_array_t,p_previous json_array_t) return json_array_t is
      l_union json_array_t := json_array_t();
      l_result json_array_t := json_array_t();
      l_value varchar2(200);
      l_override varchar2(400);
      l_current_has boolean;
      l_previous_has boolean;
    begin
      for pass in 1..3 loop
        declare l_values json_array_t;
        begin
          l_values:=case pass when 1 then p_current when 2 then p_previous else p_source end;
          for n in 0..l_values.get_size-1 loop
            l_value:=l_values.get_string(n);
            if not has_value(l_union,l_value) then l_union.append(l_value); end if;
          end loop;
        end;
      end loop;
      for n in 0..l_union.get_size-1 loop
        l_value:=l_union.get_string(n); l_override:='relationships.'||p_name||'.'||l_value;
        l_current_has:=has_value(p_current,l_value); l_previous_has:=has_value(p_previous,l_value);
        if l_current_has != l_previous_has then l_overrides.put(l_override,true); end if;
        if l_overrides.has(l_override) then
          if l_current_has then l_result.append(l_value); end if;
          if l_current_has != has_value(p_source,l_value) then conflict(l_override,'User relationship override preserved'); end if;
        elsif has_value(p_source,l_value) then l_result.append(l_value);
        end if;
      end loop;
      return sorted_values(l_result);
    end;

    procedure validate_source_line(p_value json_object_t);

    function merge(p_source json_object_t,p_current json_object_t,p_previous json_object_t) return json_object_t is
      l_fields json_object_t := treat(p_current.get_object('fields').clone as json_object_t);
      l_source_fields json_object_t := p_source.get_object('fields');
      l_previous_fields json_object_t := p_previous.get_object('fields');
      l_sets json_object_t := json_object_t();
      l_keys json_key_list;
      l_name varchar2(400);
      l_coupled boolean := false;
      l_owner_checked boolean := false;
      l_reference number;
      l_result json_object_t := json_object_t();
    begin
      l_keys:=l_source_fields.get_keys;
      for n in 1..l_keys.count loop
        l_name:=l_keys(n);
        if l_kind='VARIATION' and l_name in ('owner_key','owner_kind')
          and not equal_json(l_fields.get(l_name),l_source_fields.get(l_name))
        then
          if not l_owner_checked then
            if l_source_fields.get_string('owner_key') is null or l_source_fields.get_string('owner_kind') is null
              or l_source_fields.get_string('owner_kind') not in ('OPENING','GAMBIT')
            then raise_application_error(-20022,'Variation requires exactly one valid source owner'); end if;
            l_reference:=resolve_key(l_source_fields.get_string('owner_key'),l_source_fields.get_string('owner_kind'));
            l_reference:=resolve_key(l_source_fields.get_string('parent_key'),'VARIATION');
            validate_source_line(p_source);
            conflict('topology','Public writer cannot change variation ownership; coupled move and parent fields retained');
            l_owner_checked:=true;
          end if;
          l_coupled:=true;
        end if;
        if l_overrides.has('fields.'||l_name) or
          (not (l_name='strategy' and l_kind in ('OPENING','GAMBIT')
             and not l_previous_fields.has('strategy') and l_fields.get_clob('strategy') is null)
           and not equal_json(l_fields.get(l_name),l_previous_fields.get(l_name))) then
          l_overrides.put('fields.'||l_name,true);
          if l_kind='VARIATION' and l_name in ('pgn','line_kind','branch_ply','starting_fen','parent_key','owner_kind','owner_key') then l_coupled:=true; end if;
        end if;
      end loop;
      if l_coupled then
        for n in 1..l_keys.count loop
          if l_keys(n) in ('pgn','line_kind','branch_ply','starting_fen','parent_key','owner_kind','owner_key') then l_overrides.put('fields.'||l_keys(n),true); end if;
        end loop;
      end if;
      for n in 1..l_keys.count loop
        l_name:=l_keys(n);
        if l_overrides.has('fields.'||l_name) then
          if not equal_json(l_fields.get(l_name),l_source_fields.get(l_name)) then conflict(l_name,'User field override preserved'); end if;
        elsif l_kind='VARIATION' and l_name in ('owner_key','owner_kind') and not equal_json(l_fields.get(l_name),l_source_fields.get(l_name)) then
          conflict(l_name,'Ordinary API cannot change variation ownership'); l_overrides.put('fields.'||l_name,true);
        else l_fields.put(l_name,l_source_fields.get(l_name));
        end if;
      end loop;
      l_keys:=p_source.get_object('relationships').get_keys;
      for n in 1..l_keys.count loop
        l_name:=l_keys(n);
        l_sets.put(l_name,merge_set(l_name,p_source.get_object('relationships').get_array(l_name),
          p_current.get_object('relationships').get_array(l_name),p_previous.get_object('relationships').get_array(l_name)));
      end loop;
      l_result.put('fields',l_fields); l_result.put('relationships',l_sets); return l_result;
    end;

    procedure validate_variation(p_value json_object_t) is
      l_fields json_object_t:=p_value.get_object('fields');
      l_parent_key varchar2(100):=l_fields.get_string('parent_key');
      l_parent json_object_t;
      l_root json_object_t:=l_fields;
      l_parent_pgn clob;
      l_pgn clob:=l_fields.get_clob('pgn');
      l_fen varchar2(200);
      l_walk varchar2(100):=l_parent_key;
      l_parent_id number;
      l_ignored number;
      l_owner_id number;
      l_visited bool_map;
    begin
      if l_fields.get_string('owner_kind') is null or l_fields.get_string('owner_kind') not in ('OPENING','GAMBIT') or l_fields.get_string('owner_key') is null then
        raise_application_error(-20022,'Variation requires exactly one valid owner');
      end if;
      l_owner_id:=resolve_key(l_fields.get_string('owner_key'),l_fields.get_string('owner_kind'));
      while l_walk is not null loop
        if l_visited.exists(l_walk) then raise_application_error(-20024,'Cyclic desired variation dependencies'); end if;
        l_visited(l_walk):=true;
        l_parent_id:=resolve_key(l_walk,'VARIATION');
        if l_states.exists(l_walk) then l_parent:=l_states(l_walk).get_object('fields');
        else l_parent:=snapshot('VARIATION',l_parent_id,l_ignored).get_object('fields'); end if;
        if l_walk=l_parent_key then
          l_parent_pgn:=l_parent.get_clob('pgn');
          if l_parent.get_string('owner_key')!=l_fields.get_string('owner_key') or l_parent.get_string('owner_kind')!=l_fields.get_string('owner_kind') then
            raise_application_error(-20022,'Variation parent belongs to a different owner');
          end if;
        end if;
        l_root:=l_parent; l_walk:=l_parent.get_string('parent_key');
      end loop;
      l_fen:=l_root.get_string('starting_fen');
      if l_parent_key is not null then
        if l_fields.get_string('starting_fen') is not null then raise_application_error(-20023,'Only roots may define FEN'); end if;
        if l_fields.get_string('line_kind')='CONTINUATION' then
          chess_validation_api.validate_continuation(l_parent_pgn,l_pgn,l_fields.get_number('branch_ply'),l_fen);
        elsif l_fields.get_string('line_kind')='ALTERNATIVE' then
          chess_validation_api.validate_branch(l_parent_pgn,l_pgn,l_fields.get_number('branch_ply'),l_fen);
        else raise_application_error(-20014,'Child requires ALTERNATIVE or CONTINUATION'); end if;
      elsif l_fields.get_string('line_kind')!='MAIN' or l_fields.get_number('branch_ply') is not null then
        raise_application_error(-20014,'Root requires MAIN and no branch ply');
      end if;
      chess_validation_api.validate_pgn(l_pgn,true,l_fen);
    end;

    function topology(p_fields json_object_t) return json_object_t is
      l_result json_object_t:=json_object_t();
      l_keys json_key_list:=p_fields.get_keys;
    begin
      for n in 1..l_keys.count loop
        if l_keys(n) in ('pgn','line_kind','branch_ply','starting_fen','parent_key','owner_kind','owner_key') then
          l_result.put(l_keys(n),p_fields.get(l_keys(n)));
        end if;
      end loop;
      return l_result;
    end;

    procedure validate_source_line(p_value json_object_t) is
      l_fields json_object_t:=p_value.get_object('fields');
      l_pgn clob:=l_fields.get_clob('pgn');
      l_fen varchar2(200);
    begin
      -- Separate malformed source from a valid line incompatible with retained target context.
      l_fen:=chess_validation_api.pgn_header(l_pgn,'FEN');
      chess_validation_api.validate_pgn(l_pgn,true,l_fen);
    end;

    function effective_root_fen(p_fields json_object_t) return varchar2 is
      l_fields json_object_t:=p_fields;
      l_parent varchar2(100):=l_fields.get_string('parent_key');
      l_parent_id number;
      l_ignored number;
      l_visited bool_map;
    begin
      while l_parent is not null loop
        if l_visited.exists(l_parent) then raise_application_error(-20024,'Cyclic desired variation dependencies'); end if;
        l_visited(l_parent):=true;
        l_parent_id:=resolve_key(l_parent,'VARIATION');
        if l_states.exists(l_parent) then l_fields:=l_states(l_parent).get_object('fields');
        else l_fields:=snapshot('VARIATION',l_parent_id,l_ignored).get_object('fields'); end if;
        l_parent:=l_fields.get_string('parent_key');
      end loop;
      return l_fields.get_string('starting_fen');
    end;

    procedure freeze_topology(p_value in out nocopy json_object_t,p_current json_object_t,p_reason varchar2) is
      l_fields json_object_t:=p_value.get_object('fields');
      l_current_fields json_object_t:=p_current.get_object('fields');
      l_keys json_key_list:=l_fields.get_keys;
    begin
      for n in 1..l_keys.count loop
        if l_keys(n) in ('pgn','line_kind','branch_ply','starting_fen','parent_key','owner_kind','owner_key') then
          l_fields.put(l_keys(n),l_current_fields.get(l_keys(n)));
          l_overrides.put('fields.'||l_keys(n),true);
        end if;
      end loop;
      p_value.put('fields',l_fields);
      l_overrides.put('unsupported_topology',true);
      l_frozen_topology(l_key):=true;
      conflict('topology',p_reason);
    end;

    procedure guard_retained_topology(p_value in out nocopy json_object_t,p_current json_object_t) is
      l_fields json_object_t:=p_value.get_object('fields');
      l_current_fields json_object_t:=p_current.get_object('fields');
      l_source_fields json_object_t:=l_desired.get_object('fields');
      l_parent varchar2(100):=l_fields.get_string('parent_key');
      l_fen varchar2(200);
      l_pgn clob;
      l_owner number;
    begin
      if l_kind!='VARIATION' then return; end if;
      if equal_json(topology(l_fields),topology(l_current_fields)) then
        if not equal_json(topology(l_source_fields),topology(l_current_fields)) then
          -- Only a retained, not a successfully applied, context protects descendants.
          l_frozen_topology(l_key):=true;
        end if;
        return;
      end if;
      validate_source_line(p_value);
      if l_fields.get_string('owner_kind')!=l_current_fields.get_string('owner_kind')
        or l_fields.get_string('owner_key')!=l_current_fields.get_string('owner_key') then
        l_owner:=resolve_key(l_fields.get_string('owner_key'),l_fields.get_string('owner_kind'));
        freeze_topology(p_value,p_current,'Public writer cannot change variation ownership; coupled topology retained');
        return;
      end if;
      begin
        validate_variation(p_value);
      exception when others then
        if sqlcode in (-20021,-20022,-20025) and l_parent is not null and l_frozen_topology.exists(l_parent) then
          freeze_topology(p_value,p_current,'Source topology depends on a retained parent context; independent fields remain applicable');
          return;
        end if;
        raise;
      end;
      l_fen:=effective_root_fen(l_fields); l_pgn:=l_fields.get_clob('pgn');
      for child in (select pgn,line_kind,branch_ply from orac_chess.chess_variation_v where parent_variation_id=l_id) loop
        begin
          if child.line_kind='CONTINUATION' then chess_validation_api.validate_continuation(l_pgn,child.pgn,child.branch_ply,l_fen);
          else chess_validation_api.validate_branch(l_pgn,child.pgn,child.branch_ply,l_fen); end if;
        exception when others then
          if sqlcode in (-20021,-20025) then
            freeze_topology(p_value,p_current,'Public writer cannot atomically replace this topology with incompatible retained descendants; independent fields remain applicable');
            return;
          end if;
          raise;
        end;
      end loop;
    end;

    function new_topology_supported(p_value json_object_t) return boolean is
      l_fields json_object_t:=p_value.get_object('fields');
      l_parent varchar2(100):=l_fields.get_string('parent_key');
    begin
      if l_kind!='VARIATION' or l_parent is null or not l_frozen_topology.exists(l_parent) then return true; end if;
      validate_source_line(p_value);
      begin validate_variation(p_value);
      exception when others then
        if sqlcode in (-20021,-20022,-20025) then
          l_blocked(l_key):=true; l_skipped:=l_skipped+1;
          conflict('topology','New line is incompatible with retained parent topology; entry and dependent descendants skipped');
          return false;
        end if;
        raise;
      end;
      return true;
    end;

    procedure validate_sets(p_value json_object_t);

    procedure save_entity(p_value json_object_t,p_existing json_object_t) is
      l_fields json_object_t := p_value.get_object('fields');
      l_sets json_object_t := p_value.get_object('relationships');
      l_owner number;
      l_opening number;
      l_gambit number;
      l_parent number;
      l_description clob;
      l_strategy clob;
      l_pgn clob;
      l_annotation clob;
      l_write boolean := p_existing is null;
    begin
      if p_existing is not null then
        l_write:=not equal_json(l_fields,p_existing.get('fields'));
        if l_kind!='OPENING' then l_write:=l_write or not equal_json(l_sets.get('eco_codes'),p_existing.get_object('relationships').get('eco_codes')); end if;
      end if;
      validate_sets(p_value);
      if not l_write then return; end if;
      if l_kind='VARIATION' then validate_variation(p_value); end if;
      if not p_apply then
        if l_id is null then l_id:=l_virtual; l_virtual:=l_virtual-1; end if;
        return;
      end if;
      l_strategy:=l_fields.get_clob('strategy');
      if l_kind='OPENING' then
        l_parent:=resolve_key(l_fields.get_string('parent_key'),'OPENING'); l_description:=l_fields.get_clob('description');
        orac_chess.chess_admin_api.save_opening(l_id,l_version,l_fields.get_string('name'),l_fields.get_string('opening_type'),l_description,l_strategy,l_parent,l_next);
      elsif l_kind='GAMBIT' then
        l_description:=l_fields.get_clob('description');
        orac_chess.chess_admin_api.save_gambit_with_eco(l_id,l_version,l_fields.get_string('name'),l_description,l_strategy,selection(l_sets.get_array('eco_codes')),l_next);
      else
        l_owner:=resolve_key(l_fields.get_string('owner_key'),l_fields.get_string('owner_kind')); l_parent:=resolve_key(l_fields.get_string('parent_key'),'VARIATION');
        if l_fields.get_string('owner_kind')='OPENING' then l_opening:=l_owner; else l_gambit:=l_owner; end if;
        l_pgn:=l_fields.get_clob('pgn'); l_annotation:=l_fields.get_clob('annotation');
        orac_chess.chess_variation_api.save_variation_with_eco(l_id,l_version,l_opening,l_gambit,l_parent,l_fields.get_number('branch_ply'),
          l_fields.get_string('name'),l_fields.get_string('line_kind'),l_pgn,l_fields.get_string('starting_fen'),l_annotation,selection(l_sets.get_array('eco_codes')),l_next);
      end if;
      l_version:=l_next;
    end;

    procedure validate_sets(p_value json_object_t) is
      l_sets json_object_t:=p_value.get_object('relationships');
      l_keys json_key_list:=l_sets.get_keys;
      l_values json_array_t;
      l_code varchar2(200);
      l_target number;
      l_count number;
    begin
      for n in 1..l_keys.count loop
        l_values:=l_sets.get_array(l_keys(n));
        if l_keys(n)='opening_keys' then
          for j in 0..l_values.get_size-1 loop l_target:=resolve_key(l_values.get_string(j),'OPENING'); end loop;
        elsif l_keys(n)='eco_codes' then
          for j in 0..l_values.get_size-1 loop
            l_code:=l_values.get_string(j);
            select count(*) into l_count from orac_chess.chess_eco_code_v where eco_code=l_code;
            if l_count!=1 then raise_application_error(-20013,'Unknown source ECO reference'); end if;
          end loop;
        elsif l_keys(n)!='aliases' then raise_application_error(-20014,'Unsupported catalogue relationship');
        end if;
      end loop;
    end;

    procedure save_sets(p_value json_object_t,p_current json_object_t) is
      l_names json_key_list := p_value.get_object('relationships').get_keys;
      l_values json_array_t;
      l_existing json_array_t;
      l_value varchar2(200);
      l_name varchar2(200);
      l_target number;
      l_link boolean;
    begin
      if not p_apply then return; end if;
      for n in 1..l_names.count loop
        l_name:=l_names(n);
        if l_kind='OPENING' or l_name='opening_keys' then
          l_values:=p_value.get_object('relationships').get_array(l_name);
          l_existing:=p_current.get_object('relationships').get_array(l_name);
          for pass in 1..2 loop
            declare l_scan json_array_t;
            begin
              l_scan:=case when pass=1 then l_existing else l_values end;
              for j in 0..l_scan.get_size-1 loop
                l_value:=l_scan.get_string(j); l_link:=pass=2;
                if (l_link and not has_value(l_existing,l_value)) or (not l_link and not has_value(l_values,l_value)) then
                  if l_kind='OPENING' and l_name='eco_codes' then
                    orac_chess.chess_admin_api.link_opening_eco(l_id,l_value,l_version,l_link,l_next);
                  elsif l_kind='OPENING' and l_name='aliases' then
                    orac_chess.chess_admin_api.link_opening_alias(l_id,l_value,l_version,l_link,l_next);
                  elsif l_kind='GAMBIT' and l_name='opening_keys' then
                    l_target:=resolve_key(l_value,'OPENING');
                    orac_chess.chess_admin_api.link_gambit_opening(l_id,l_target,l_version,l_link,l_next);
                  else raise_application_error(-20014,'Unsupported catalogue relationship');
                  end if;
                  l_version:=l_next;
                end if;
              end loop;
            end;
          end loop;
        end if;
      end loop;
    end;

    procedure count_relationship_changes(p_before json_object_t,p_after json_object_t) is
      l_before json_object_t:=p_before.get_object('relationships');
      l_after json_object_t:=p_after.get_object('relationships');
      l_keys json_key_list:=l_after.get_keys;
      l_old_values json_array_t;
      l_new_values json_array_t;
      l_old_parent varchar2(100):=p_before.get_object('fields').get_string('parent_key');
      l_new_parent varchar2(100):=p_after.get_object('fields').get_string('parent_key');
      l_old_owner varchar2(200);
      l_new_owner varchar2(200);
    begin
      for n in 1..l_keys.count loop
        l_old_values:=l_before.get_array(l_keys(n)); l_new_values:=l_after.get_array(l_keys(n));
        for j in 0..l_new_values.get_size-1 loop
          if not has_value(l_old_values,l_new_values.get_string(j)) then l_relationships_added:=l_relationships_added+1; end if;
        end loop;
        for j in 0..l_old_values.get_size-1 loop
          if not has_value(l_new_values,l_old_values.get_string(j)) then l_relationships_removed:=l_relationships_removed+1; end if;
        end loop;
      end loop;
      if l_kind='VARIATION' then
        if p_before.get_object('fields').get_string('owner_key') is not null then
          l_old_owner:=p_before.get_object('fields').get_string('owner_kind')||':'||p_before.get_object('fields').get_string('owner_key');
        end if;
        if p_after.get_object('fields').get_string('owner_key') is not null then
          l_new_owner:=p_after.get_object('fields').get_string('owner_kind')||':'||p_after.get_object('fields').get_string('owner_key');
        end if;
        if nvl(l_old_owner,chr(1))!=nvl(l_new_owner,chr(1)) then
          if l_old_owner is not null then l_owner_edges_removed:=l_owner_edges_removed+1; end if;
          if l_new_owner is not null then l_owner_edges_added:=l_owner_edges_added+1; end if;
        end if;
      end if;
      if nvl(l_old_parent,chr(1))!=nvl(l_new_parent,chr(1)) then
        if l_old_parent is not null then l_parent_edges_removed:=l_parent_edges_removed+1; end if;
        if l_new_parent is not null then l_parent_edges_added:=l_parent_edges_added+1; end if;
      end if;
    end;

    function empty_snapshot(p_source json_object_t) return json_object_t is
      l_result json_object_t:=json_object_t(); l_sets json_object_t:=json_object_t();
      l_keys json_key_list:=p_source.get_object('relationships').get_keys;
    begin
      for n in 1..l_keys.count loop l_sets.put(l_keys(n),json_array_t()); end loop;
      l_result.put('fields',json_object_t()); l_result.put('relationships',l_sets); return l_result;
    end;

    function find_existing return number is
      l_found number;
      l_fields json_object_t:=l_desired.get_object('fields');
      l_name varchar2(200):=l_fields.get_string('name');
      l_owner number;
      l_owner_kind varchar2(12);
    begin
      if l_kind='OPENING' then
        select opening_id into l_found from orac_chess.chess_opening_v where name=l_name;
      elsif l_kind='GAMBIT' then
        select gambit_id into l_found from orac_chess.chess_gambit_v where name=l_name;
      else
        l_owner:=resolve_key(l_fields.get_string('owner_key'),l_fields.get_string('owner_kind')); l_owner_kind:=l_fields.get_string('owner_kind');
        if l_owner<0 then return null; end if;
        if l_fields.get_string('line_kind')='MAIN' then
          select variation_id into l_found from orac_chess.chess_variation_v where parent_variation_id is null and line_kind='MAIN'
            and ((l_owner_kind='OPENING' and opening_id=l_owner) or (l_owner_kind='GAMBIT' and gambit_id=l_owner));
        else
          select variation_id into l_found from orac_chess.chess_variation_v where name=l_name
            and ((l_owner_kind='OPENING' and opening_id=l_owner) or (l_owner_kind='GAMBIT' and gambit_id=l_owner));
        end if;
      end if;
      return l_found;
    exception when no_data_found then return null;
    end;
  begin
    dbms_application_info.read_module(l_old_module,l_old_action);
    dbms_application_info.set_module('Orac Chess catalogue',case when p_apply then 'apply' else 'plan' end);
    l_application_info_set:=true;
    if p_apply then savepoint chess_catalogue_sync; chess_validation_api.lock_control; end if;
    if l_revision is null then raise_application_error(-20014,'Catalogue source revision is required'); end if;
    for i in 0..l_entries.get_size-1 loop
      dbms_application_info.set_action(substr(case when p_apply then 'apply ' else 'plan ' end||to_char(i+1)||'/'||to_char(l_entries.get_size),1,32));
      l_item:=treat(l_entries.get(i) as json_object_t); l_key:=l_item.get_string('key'); l_kind:=l_item.get_string('kind');
      l_source:=l_item.get_object('desired'); l_desired:=json_object_t.parse(l_source.to_clob); l_id:=null; l_version:=null; l_ownership:=null;
      if l_key is null or l_kind is null or not regexp_like(l_key,'^[a-z0-9_]{1,100}$') or l_kind not in ('OPENING','GAMBIT','VARIATION') then raise_application_error(-20014,'Invalid catalogue identity'); end if;
      if l_seen.exists(l_key) then raise_application_error(-20009,'Duplicate catalogue key: '||l_key); end if;
      l_seen(l_key):=true;
      if l_item.get_string('source_hash') is null or not regexp_like(l_item.get_string('source_hash'),'^[0-9a-f]{64}$') then raise_application_error(-20014,'Invalid semantic source hash'); end if;
      l_hash:=hextoraw(l_item.get_string('source_hash'));
      declare
        l_fields json_object_t:=l_desired.get_object('fields');
        l_sets json_object_t:=l_desired.get_object('relationships');
        l_keys json_key_list:=l_fields.get_keys;
        l_name varchar2(400);
        l_supported boolean;
      begin
        for n in 1..l_keys.count loop
          l_name:=l_keys(n);
          l_supported:=(l_kind='OPENING' and l_name in ('name','description','strategy','opening_type','parent_key'))
            or (l_kind='GAMBIT' and l_name in ('name','description','strategy'))
            or (l_kind='VARIATION' and l_name in ('name','annotation','pgn','line_kind','branch_ply','starting_fen','owner_kind','owner_key','parent_key'));
          if not l_supported then conflict(l_name,'Field is not supported by the public writer'); l_fields.remove(l_name); end if;
        end loop;
        l_keys:=l_sets.get_keys;
        for n in 1..l_keys.count loop
          l_name:=l_keys(n);
          l_supported:=l_name='eco_codes' or (l_kind='OPENING' and l_name='aliases') or (l_kind='GAMBIT' and l_name='opening_keys');
          if not l_supported then conflict(l_name,'Relationship is not supported by the public writer'); l_sets.remove(l_name); end if;
        end loop;
        for name in (select 'parent_key' value from dual union all select 'owner_key' from dual) loop
          if l_fields.has(name.value) and l_fields.get_string(name.value) is not null
            and not regexp_like(l_fields.get_string(name.value),'^[a-z0-9_]{1,100}$')
          then raise_application_error(-20014,'Source dependencies require stable catalogue keys'); end if;
        end loop;
        if l_sets.has('opening_keys') then
          declare l_values json_array_t:=l_sets.get_array('opening_keys');
          begin
            for n in 0..l_values.get_size-1 loop
              if not regexp_like(l_values.get_string(n),'^[a-z0-9_]{1,100}$') then raise_application_error(-20014,'Source edges require stable catalogue keys'); end if;
            end loop;
          end;
        end if;
        l_desired.put('fields',l_fields); l_desired.put('relationships',l_sets);
      end;

      l_has_old:=true;
      begin select * into l_old from orac_chess.chess_catalogue_entry where catalogue_key=l_key;
      exception when no_data_found then l_has_old:=false; end;
      l_overrides:=json_object_t();
      if l_has_old and l_old.entity_kind!=l_kind then raise_application_error(-20014,'Catalogue key changed entity kind'); end if;
      if l_has_old and coalesce(l_old.opening_id,l_old.gambit_id,l_old.variation_id) is null then
        l_tombstones:=l_tombstones+1; l_blocked(l_key):=true;
        conflict('entity','Deleted tracked identity is not recreated'); continue;
      end if;
      declare
        l_fields json_object_t:=l_desired.get_object('fields');
        l_block boolean:=false;
      begin
        if deleted_dependency(l_fields.get_string('parent_key')) then conflict('parent_key','Deleted or blocked parent; dependent entry skipped'); l_block:=true; end if;
        if l_kind='VARIATION' and deleted_dependency(l_fields.get_string('owner_key')) then conflict('owner_key','Deleted owner; dependent entry skipped'); l_block:=true; end if;
        if l_block then l_blocked(l_key):=true; l_skipped:=l_skipped+1; continue; end if;
        if l_kind='GAMBIT' then
          declare
            l_sets json_object_t:=l_desired.get_object('relationships');
            l_values json_array_t:=l_sets.get_array('opening_keys');
            l_retained json_array_t:=json_array_t();
            l_value varchar2(100);
          begin
            for n in 0..l_values.get_size-1 loop
              l_value:=l_values.get_string(n);
              if deleted_dependency(l_value) then conflict('relationships.opening_keys.'||l_value,'Deleted endpoint; source edge skipped');
              else l_retained.append(l_value); end if;
            end loop;
            l_sets.put('opening_keys',l_retained); l_desired.put('relationships',l_sets);
          end;
        end if;
      end;
      if l_has_old then
        if l_old.entity_kind!=l_kind then raise_application_error(-20014,'Catalogue key changed entity kind'); end if;
        l_id:=coalesce(l_old.opening_id,l_old.gambit_id,l_old.variation_id); l_ownership:=l_old.ownership;
        if l_id is null then l_tombstones:=l_tombstones+1; l_blocked(l_key):=true; conflict('entity','Deleted tracked identity is not recreated'); continue; end if;
        l_baseline:=json_object_t.parse(l_old.baseline_json); l_applied:=l_baseline.get_object('applied'); l_overrides:=l_baseline.get_object('overrides');
      else
        l_id:=find_existing;
        l_ownership:=case when l_id is null then 'CREATED' else 'ADOPTED' end;
      end if;
      if l_id is null then
        l_current:=empty_snapshot(l_desired); l_merged:=l_desired;
        if not new_topology_supported(l_merged) then continue; end if;
        save_entity(l_merged,null); save_sets(l_merged,l_current);
        l_created:=l_created+1;
      else
        l_current:=snapshot(l_kind,l_id,l_version);
        if not l_has_old then
          l_applied:=treat(l_current.clone as json_object_t); l_adopted:=l_adopted+1;
          if l_kind in ('OPENING','GAMBIT') and l_current.get_object('fields').get_clob('strategy') is null then
            declare l_fields json_object_t:=l_applied.get_object('fields');
            begin l_fields.remove('strategy'); l_applied.put('fields',l_fields); end;
          end if;
        end if;
        if l_ownership='ADOPTED' then
          -- Scalar fields remain protected forever; pre-adoption edges remain user-owned.
          declare
            l_fields json_object_t:=l_desired.get_object('fields');
            l_sets json_object_t:=l_current.get_object('relationships');
            l_keys json_key_list:=l_fields.get_keys;
            l_values json_array_t;
          begin
            for n in 1..l_keys.count loop
              if l_keys(n)!='strategy' or
                (not l_applied.get_object('fields').has('strategy')
                 and l_current.get_object('fields').get_clob('strategy') is not null)
              then l_overrides.put('fields.'||l_keys(n),true); end if;
            end loop;
            if not l_has_old then
              l_keys:=l_sets.get_keys;
              for n in 1..l_keys.count loop
                l_values:=l_sets.get_array(l_keys(n));
                for j in 0..l_values.get_size-1 loop l_overrides.put('relationships.'||l_keys(n)||'.'||l_values.get_string(j),true); end loop;
              end loop;
            end if;
            -- Existing gambit/variation direct ECO is creation-only, as in the starter contract.
            if l_kind!='OPENING' then
              l_values:=l_desired.get_object('relationships').get_array('eco_codes');
              for j in 0..l_values.get_size-1 loop l_overrides.put('relationships.eco_codes.'||l_values.get_string(j),true); end loop;
            end if;
          end;
        end if;
        l_merged:=merge(l_desired,l_current,l_applied);
        if l_has_old and l_old.last_source_hash=l_hash and equal_json(l_source,l_baseline.get('source')) then
          -- User-local changes and API canonicalisation never trigger same-source writes.
          l_merged:=l_current;
        end if;
        guard_retained_topology(l_merged,l_current);
        if not equal_json(l_merged,l_current) then
          save_entity(l_merged,l_current); save_sets(l_merged,l_current); l_updated:=l_updated+1;
        else l_unchanged:=l_unchanged+1;
        end if;
      end if;
      if p_apply then l_merged:=snapshot(l_kind,l_id,l_version); end if;
      count_relationship_changes(l_current,l_merged);
      l_states(l_key):=l_merged;
      l_kinds(l_key):=l_kind;
      l_ids(l_key):=l_id; l_reverse(l_kind||':'||to_char(l_id)):=l_key;
      -- Actual applied baseline contains only the final merged values, never skipped source values.
      l_snapshot:=json_object_t(); l_snapshot.put('source',l_source); l_snapshot.put('applied',l_merged); l_snapshot.put('overrides',l_overrides);
      l_snapshot.put('row_version',l_version);
      l_metadata_changed:=not l_has_old;
      if l_has_old then
        -- An unchanged upstream snapshot is a report-only run, even after local edits.
        -- Re-detect overrides against the retained applied baseline on the next source change.
        l_metadata_changed:=l_old.last_source_hash!=l_hash or not equal_json(l_snapshot.get('source'),l_baseline.get('source'));
      end if;
      if l_metadata_changed then
        l_pending(l_key).entity_kind:=l_kind; l_pending(l_key).entity_id:=l_id; l_pending(l_key).ownership:=l_ownership;
        l_pending(l_key).source_hash:=l_hash; l_pending(l_key).baseline:=l_snapshot.to_clob;
      end if;
    end loop;
    for existing in (select catalogue_key from orac_chess.chess_catalogue_entry order by catalogue_key) loop
      if not l_seen.exists(existing.catalogue_key) then l_deprecated.append(existing.catalogue_key); end if;
    end loop;
    -- Domain writes and all validations finish before any ledger metadata is changed.
    if p_apply then
      l_key:=l_pending.first;
      while l_key is not null loop
        merge into orac_chess.chess_catalogue_entry target
        using (select l_key catalogue_key from dual) incoming on (target.catalogue_key=incoming.catalogue_key)
        when matched then update set entity_kind=l_pending(l_key).entity_kind,
          opening_id=case when l_pending(l_key).entity_kind='OPENING' then l_pending(l_key).entity_id end,
          gambit_id=case when l_pending(l_key).entity_kind='GAMBIT' then l_pending(l_key).entity_id end,
          variation_id=case when l_pending(l_key).entity_kind='VARIATION' then l_pending(l_key).entity_id end,
          ownership=l_pending(l_key).ownership,source_revision=l_revision,last_source_hash=l_pending(l_key).source_hash,baseline_json=l_pending(l_key).baseline
        when not matched then insert (catalogue_key,entity_kind,opening_id,gambit_id,variation_id,ownership,source_revision,last_source_hash,baseline_json)
        values (l_key,l_pending(l_key).entity_kind,
          case when l_pending(l_key).entity_kind='OPENING' then l_pending(l_key).entity_id end,
          case when l_pending(l_key).entity_kind='GAMBIT' then l_pending(l_key).entity_id end,
          case when l_pending(l_key).entity_kind='VARIATION' then l_pending(l_key).entity_id end,
          l_pending(l_key).ownership,l_revision,l_pending(l_key).source_hash,l_pending(l_key).baseline);
        l_key:=l_pending.next(l_key);
      end loop;
    end if;
    l_report.put('dry_run',not p_apply); l_report.put('created',l_created); l_report.put('updated',l_updated);
    l_report.put('adopted',l_adopted); l_report.put('unchanged',l_unchanged); l_report.put('tombstones',l_tombstones);
    l_report.put('source_revision',l_revision); l_report.put('skipped',l_skipped);
    l_report.put('relationships_added',l_relationships_added); l_report.put('relationships_removed',l_relationships_removed);
    l_report.put('parent_edges_added',l_parent_edges_added); l_report.put('parent_edges_removed',l_parent_edges_removed);
    l_report.put('owner_edges_added',l_owner_edges_added); l_report.put('owner_edges_removed',l_owner_edges_removed);
    l_report.put('skipped_records',l_skipped+l_tombstones);
    l_report.put('conflicting_record_count',l_conflicted_keys.count); l_report.put('conflict_detail_count',l_conflicts.get_size);
    l_report.put('validation_failures',0);
    l_report.put('ledger_changes',l_pending.count); l_report.put('conflicts',l_conflicts); l_report.put('deprecated',l_deprecated);
    p_report:=l_report.to_clob;
    dbms_application_info.set_module(l_old_module,l_old_action);
  exception when others then
    declare
      l_error_code number:=sqlcode;
      l_error_text varchar2(1800):=substr(sqlerrm,1,1500);
    begin
      if p_apply then rollback to chess_catalogue_sync; end if;
      if l_application_info_set then dbms_application_info.set_module(l_old_module,l_old_action); end if;
      if l_error_code between -20999 and -20000 then
        raise_application_error(l_error_code,substr('Catalogue key '||nvl(l_key,'payload')||': '||l_error_text,1,1800),true);
      else
        raise_application_error(-20002,substr('Catalogue key '||nvl(l_key,'payload')||': '||l_error_text,1,1800),true);
      end if;
    end;
  end;

  procedure plan_catalogue(p_payload clob,p_report out clob) is
  begin synchronise(p_payload,false,p_report); end;
  procedure apply_catalogue(p_payload clob,p_report out clob) is
  begin synchronise(p_payload,true,p_report); end;
end chess_catalogue_api;
/
--rollback empty
