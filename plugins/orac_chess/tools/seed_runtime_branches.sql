--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 10-Nov-2026
-- Description: Generated immutable Chess CSV seed batch; regenerate with tools/generate_seed.py.
-- Purpose: Insert missing catalogue data through public administration APIs, preserving user edits.
-- Usage: Managed plugin install/upgrade through db/liquibase/pluginController.xml.
--changeset clive:orac_chess_seed_@BATCH@ context:plugin,prod labels:plugin stripComments:false endDelimiter:/
declare
  l_payload clob;
  l_description clob;
  l_batch json_object_t;
  l_rows json_array_t;
  l_row json_object_t;
  l_context varchar2(1000);
  l_id number;
  l_name varchar2(500);
  l_platform varchar2(50);
  l_external varchar2(255);
  l_version number;
  l_next number;
  l_count number;
  l_created number := 0;
  l_skipped number := 0;
  type id_set is table of boolean index by varchar2(100);
  l_new_openings id_set;
  type branch_ids is table of number index by varchar2(200);
  l_branch_ids branch_ids;
  l_branch_skips id_set;

  procedure release_clob(p_value in out nocopy clob) is
  begin
    if dbms_lob.istemporary(p_value) = 1
    then
      dbms_lob.freetemporary(p_value);
    end if;
    p_value := null;
  end;

  function txt(p_row json_object_t, p_key varchar2) return varchar2 is
  begin
    return p_row.get_string(p_key);
  end;

  function eco_selection(p_row json_object_t, p_key varchar2) return varchar2 is
    l_values json_array_t;
    l_result varchar2(32767);
  begin
    if not p_row.has(p_key) then return null; end if;
    l_values := p_row.get_array(p_key);
    for j in 0..l_values.get_size - 1 loop
      if l_result is not null then l_result := l_result || ':'; end if;
      l_result := l_result || l_values.get_string(j);
    end loop;
    return l_result;
  end;

  function opening_id(p_name varchar2) return number is
    l_result number;
  begin
    select opening_id into l_result from orac_chess.chess_opening_v where name = p_name;
    return l_result;
  exception
    when no_data_found then
      raise_application_error(-20001, 'Unknown opening name: ' || substr(p_name,1,200));
  end;

  function gambit_id(p_name varchar2) return number is
    l_result number;
  begin
    select gambit_id into l_result from orac_chess.chess_gambit_v where name = p_name;
    return l_result;
  exception
    when no_data_found then
      raise_application_error(-20001, 'Unknown gambit name: ' || substr(p_name,1,200));
  end;

  procedure source(p_creator varchar2) is
  begin
    if p_creator is null
    then
      return;
    end if;
    select count(*) into l_count from orac_chess.chess_content_source_v where creator = p_creator;
    if l_count = 0
    then
      orac_chess.chess_admin_api.save_content_source(null,null,p_creator,null,null,l_next);
      l_created := l_created + 1;
    else
      l_skipped := l_skipped + 1;
    end if;
  end;

  procedure mainline(p_item json_object_t, p_opening number, p_gambit number) is
    l_variation number;
    l_pgn clob;
    l_annotation clob;
  begin
    l_pgn := p_item.get_clob('mainline_pgn');
    if nvl(dbms_lob.getlength(l_pgn),0) = 0
    then
      release_clob(l_pgn);
      return;
    end if;
    l_context := txt(p_item,'context') || ', column mainline_pgn/starting_fen';
    -- A subject owns one root MAIN. Preserve that root even if the supplied name differs.
    select count(*) into l_count from orac_chess.chess_variation_v
    where parent_variation_id is null and line_kind = 'MAIN'
      and ((opening_id = p_opening and gambit_id is null)
        or (gambit_id = p_gambit and opening_id is null));
    if l_count = 0
    then
      l_annotation := p_item.get_clob('mainline_annotation');
      if p_item.has('mainline_eco_codes') then
        orac_chess.chess_variation_api.save_variation_with_eco(l_variation,null,p_opening,p_gambit,
          null,null,txt(p_item,'mainline_name'),'MAIN',l_pgn,
          txt(p_item,'starting_fen'),l_annotation,eco_selection(p_item,'mainline_eco_codes'),l_next);
      else
        orac_chess.chess_variation_api.save_variation(l_variation,null,p_opening,p_gambit,
          null,null,txt(p_item,'mainline_name'),'MAIN',l_pgn,
          txt(p_item,'starting_fen'),l_annotation,l_next);
      end if;
      l_created := l_created + 1;
    else
      l_skipped := l_skipped + 1;
    end if;
    release_clob(l_pgn);
    release_clob(l_annotation);
  exception
    when others then
      release_clob(l_pgn);
      release_clob(l_annotation);
      raise;
  end;


  procedure branch(p_item json_object_t) is
    l_opening number;
    l_gambit number;
    l_parent number;
    l_variation number;
    l_parent_key varchar2(200) := txt(p_item,'parent_key');
    l_key varchar2(200) := txt(p_item,'key');
    l_branch_name varchar2(200) := txt(p_item,'name');
    l_pgn clob;
    l_parent_pgn clob;
    l_annotation clob;
    l_fen varchar2(200);
    l_ply number := p_item.get_number('branch_ply');
  begin
    l_context := txt(p_item,'context') || ', column pgn/parent_key';
    if txt(p_item,'owner_type') = 'OPENING'
    then
      l_opening := opening_id(txt(p_item,'owner_name'));
    else
      l_gambit := gambit_id(txt(p_item,'owner_name'));
    end if;
    if l_branch_skips.exists(l_parent_key)
    then
      l_branch_skips(l_key) := true;
      l_skipped := l_skipped + 1;
      dbms_output.put_line('Chess seed skipped descendant ' || l_key || ': incompatible ancestor');
      return;
    end if;
    select count(*),min(variation_id) into l_count,l_variation
    from orac_chess.chess_variation_v
    where name = l_branch_name
      and ((opening_id = l_opening and gambit_id is null)
        or (gambit_id = l_gambit and opening_id is null));
    if l_count > 1
    then
      raise_application_error(-20001,'Ambiguous variation name within owner: ' || txt(p_item,'name'));
    end if;
    if l_count = 1
    then
      l_branch_ids(l_key) := l_variation;
      l_skipped := l_skipped + 1;
      return;
    end if;
    if l_parent_key = 'owner-mainline'
    then
      select count(*),min(variation_id) into l_count,l_parent
      from orac_chess.chess_variation_v
      where parent_variation_id is null and line_kind = 'MAIN'
        and ((opening_id = l_opening and gambit_id is null)
          or (gambit_id = l_gambit and opening_id is null));
      if l_count != 1
      then
        raise_application_error(-20001,'Missing or ambiguous owner mainline');
      end if;
    else
      if l_branch_skips.exists(l_parent_key)
      then
        l_branch_skips(l_key) := true;
        l_skipped := l_skipped + 1;
        dbms_output.put_line('Chess seed skipped descendant ' || l_key || ': incompatible ancestor');
        return;
      end if;
      l_parent := l_branch_ids(l_parent_key);
    end if;
    select pgn,starting_fen into l_parent_pgn,l_fen
    from orac_chess.chess_variation_v where variation_id = l_parent;
    select max(starting_fen) into l_fen from orac_chess.chess_variation_v
    where parent_variation_id is null and line_kind = 'MAIN'
      and ((opening_id = l_opening and gambit_id is null)
        or (gambit_id = l_gambit and opening_id is null));
    l_pgn := p_item.get_clob('pgn');
    begin
      -- Only a proven incompatibility is recoverable. Runtime failures remain fatal.
      if l_fen is not null
      then
        raise_application_error(-20025,'Existing mainline uses a custom starting position');
      end if;
      orac_chess.chess_validation_api.validate_branch(l_parent_pgn,l_pgn,l_ply,null);
    exception
      when others then
        if sqlcode != -20025
        then
          raise;
        end if;
        l_branch_skips(l_key) := true;
        l_skipped := l_skipped + 1;
        dbms_output.put_line('Chess seed skipped branch ' || l_key || ': incompatible edited parent');
        release_clob(l_pgn);
        release_clob(l_parent_pgn);
        return;
    end;
    l_annotation := p_item.get_clob('annotation');
    orac_chess.chess_variation_api.save_variation_with_eco(l_variation,null,l_opening,l_gambit,
      l_parent,l_ply,txt(p_item,'name'),'ALTERNATIVE',l_pgn,null,l_annotation,
      eco_selection(p_item,'eco_codes'),l_next);
    l_branch_ids(l_key) := l_variation;
    l_created := l_created + 1;
    release_clob(l_pgn);
    release_clob(l_parent_pgn);
    release_clob(l_annotation);
  exception
    when others then
      release_clob(l_pgn);
      release_clob(l_parent_pgn);
      release_clob(l_annotation);
      raise;
  end;

  procedure catalogue_links(p_item json_object_t, p_opening boolean) is
    l_values json_array_t;
    l_value varchar2(200);
    l_owner number;
    l_target number;
    l_observed number;
    l_returned number;
  begin
    if p_opening
    then
      l_owner := opening_id(txt(p_item,'name'));
      if txt(p_item,'parent_opening_name') is not null
      then
        l_context := txt(p_item,'context') || ', column parent_opening_name';
        l_target := opening_id(txt(p_item,'parent_opening_name'));
        if l_new_openings.exists(to_char(l_owner))
        then
          select row_version into l_observed from orac_chess.chess_opening_v where opening_id = l_owner;
          l_description := p_item.get_clob('description');
          orac_chess.chess_admin_api.save_opening(l_owner,l_observed,txt(p_item,'name'),
            txt(p_item,'opening_type'),l_description,l_target,l_returned);
          release_clob(l_description);
        else
          l_skipped := l_skipped + 1;
        end if;
      end if;
      for k in 1..2 loop
        if k = 1
        then
          l_values := p_item.get_array('eco_codes');
          l_context := txt(p_item,'context') || ', column eco_codes';
        else
          l_values := p_item.get_array('aliases');
          l_context := txt(p_item,'context') || ', column aliases';
        end if;
        for j in 0..l_values.get_size - 1 loop
          l_value := l_values.get_string(j);
          if k = 1
          then
            select count(*) into l_count from orac_chess.chess_opening_eco_v
            where opening_id = l_owner and eco_code = l_value;
          else
            select count(*) into l_count from orac_chess.chess_opening_alias_v
            where opening_id = l_owner and alias_name = l_value;
          end if;
          if l_count = 0
          then
            select row_version into l_observed from orac_chess.chess_opening_v where opening_id = l_owner;
            if k = 1
            then
              orac_chess.chess_admin_api.link_opening_eco(l_owner,l_value,l_observed,true,l_returned);
            else
              orac_chess.chess_admin_api.link_opening_alias(l_owner,l_value,l_observed,true,l_returned);
            end if;
            l_observed := l_returned;
            l_created := l_created + 1;
          else
            l_skipped := l_skipped + 1;
          end if;
        end loop;
      end loop;
    else
      l_owner := gambit_id(txt(p_item,'name'));
      l_values := p_item.get_array('opening_names');
      l_context := txt(p_item,'context') || ', column opening_names';
      for j in 0..l_values.get_size - 1 loop
        l_target := opening_id(l_values.get_string(j));
        select count(*) into l_count from orac_chess.chess_opening_gambit_v
        where opening_id = l_target and gambit_id = l_owner;
        if l_count = 0
        then
          select row_version into l_observed from orac_chess.chess_gambit_v where gambit_id = l_owner;
          orac_chess.chess_admin_api.link_gambit_opening(l_owner,l_target,l_observed,true,l_returned);
          l_observed := l_returned;
          l_created := l_created + 1;
        else
          l_skipped := l_skipped + 1;
        end if;
      end loop;
    end if;
  end;

  procedure video_links(p_item json_object_t, p_video number) is
    l_values json_array_t;
    l_target number;
    l_observed number;
    l_returned number;
  begin
    for k in 1..2 loop
      if k = 1
      then
        l_values := p_item.get_array('opening_names');
        l_context := txt(p_item,'context') || ', column Opening Names';
      else
        l_values := p_item.get_array('gambit_names');
        l_context := txt(p_item,'context') || ', column Gambit Names';
      end if;
      for j in 0..l_values.get_size - 1 loop
        if k = 1
        then
          l_target := opening_id(l_values.get_string(j));
          select count(*) into l_count from orac_chess.chess_video_opening_v
          where video_id = p_video and opening_id = l_target;
        else
          l_target := gambit_id(l_values.get_string(j));
          select count(*) into l_count from orac_chess.chess_video_gambit_v
          where video_id = p_video and gambit_id = l_target;
        end if;
        if l_count = 0
        then
          select row_version into l_observed from orac_chess.chess_video_v where video_id = p_video;
          if k = 1
          then
            orac_chess.chess_admin_api.link_video_opening(p_video,l_target,l_observed,true,l_returned);
          else
            orac_chess.chess_admin_api.link_video_gambit(p_video,l_target,l_observed,true,l_returned);
          end if;
          l_observed := l_returned;
          l_created := l_created + 1;
        else
          l_skipped := l_skipped + 1;
        end if;
      end loop;
    end loop;
  end;
begin
  savepoint chess_seed_batch;
-- @PAYLOAD@
  l_batch := json_object_t.parse(l_payload);
  release_clob(l_payload);
  l_rows := l_batch.get_array('videos');
  for i in 0..l_rows.get_size - 1 loop
    l_row := treat(l_rows.get(i) as json_object_t);
    l_context := txt(l_row,'context') || ', column Creator';
    source(txt(l_row,'creator'));
  end loop;
  -- Resolve all catalogue identities before parents and associations.
  for k in 1..2 loop
    if k = 1
    then
      l_rows := l_batch.get_array('openings');
    else
      l_rows := l_batch.get_array('gambits');
    end if;
    for i in 0..l_rows.get_size - 1 loop
      l_row := treat(l_rows.get(i) as json_object_t);
      l_context := txt(l_row,'context') || ', column name';
      l_id := null;
      l_name := txt(l_row,'name');
      if k = 1
      then
        select count(*) into l_count from orac_chess.chess_opening_v where name = l_name;
        if l_count = 0
        then
          l_description := l_row.get_clob('description');
          orac_chess.chess_admin_api.save_opening(l_id,null,txt(l_row,'name'),txt(l_row,'opening_type'),
            l_description,null,l_next);
          release_clob(l_description);
          l_new_openings(to_char(l_id)) := true;
        end if;
      else
        select count(*) into l_count from orac_chess.chess_gambit_v where name = l_name;
        if l_count = 0
        then
          l_description := l_row.get_clob('description');
          if l_row.has('eco_codes') then
            orac_chess.chess_admin_api.save_gambit_with_eco(l_id,null,txt(l_row,'name'),l_description,
              eco_selection(l_row,'eco_codes'),l_next);
          else
            orac_chess.chess_admin_api.save_gambit(l_id,null,txt(l_row,'name'),l_description,l_next);
          end if;
          release_clob(l_description);
        end if;
      end if;
      if l_count = 0
      then
        l_created := l_created + 1;
      else
        l_skipped := l_skipped + 1;
      end if;
    end loop;
  end loop;
  for k in 1..2 loop
    if k = 1
    then
      l_rows := l_batch.get_array('openings');
    else
      l_rows := l_batch.get_array('gambits');
    end if;
    for i in 0..l_rows.get_size - 1 loop
      l_row := treat(l_rows.get(i) as json_object_t);
      catalogue_links(l_row,k = 1);
    end loop;
  end loop;
  -- Mainlines are validated by the production PGN/FEN API after catalogue links.
  for k in 1..2 loop
    if k = 1
    then
      l_rows := l_batch.get_array('openings');
    else
      l_rows := l_batch.get_array('gambits');
    end if;
    for i in 0..l_rows.get_size - 1 loop
      l_row := treat(l_rows.get(i) as json_object_t);
      if k = 1
      then
        mainline(l_row,opening_id(txt(l_row,'name')),null);
      else
        mainline(l_row,null,gambit_id(txt(l_row,'name')));
      end if;
    end loop;
  end loop;
  l_rows := l_batch.get_array('variations');
  for i in 0..l_rows.get_size - 1 loop
    branch(treat(l_rows.get(i) as json_object_t));
  end loop;
  l_rows := l_batch.get_array('videos');
  for i in 0..l_rows.get_size - 1 loop
    l_row := treat(l_rows.get(i) as json_object_t);
    l_context := txt(l_row,'context') || ', column Platform/External Video Id';
    l_platform := txt(l_row,'platform');
    l_external := txt(l_row,'external_video_id');
    begin
      select video_id into l_id from orac_chess.chess_video_v
      where platform = l_platform and external_video_id = l_external;
      l_skipped := l_skipped + 1;
    exception
      when no_data_found then
        l_id := null;
        l_description := l_row.get_clob('description');
        orac_chess.chess_admin_api.save_video(l_id,null,txt(l_row,'platform'),txt(l_row,'external_video_id'),
          txt(l_row,'video_url'),txt(l_row,'title'),txt(l_row,'creator'),l_description,
          l_row.get_number('duration_seconds'),to_date(txt(l_row,'published_on'),'FXYYYY-MM-DD'),l_next);
        release_clob(l_description);
        l_created := l_created + 1;
    end;
    video_links(l_row,l_id);
  end loop;
  dbms_output.put_line('Chess seed @BATCH@: inserted entities/links=' || l_created || ', preserved/skipped=' || l_skipped);
exception
  when others then
    rollback to chess_seed_batch;
    release_clob(l_payload);
    release_clob(l_description);
    raise_application_error(-20002, substr('Chess seed @BATCH@ ' || l_context || ': ' || sqlerrm,1,1800));
end;
/
-- This batch is additive and user-maintained after install. Never delete data on rollback.
--rollback empty
