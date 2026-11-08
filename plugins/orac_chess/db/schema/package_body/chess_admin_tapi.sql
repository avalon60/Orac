--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_admin_tapi_body context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package body orac_chess.chess_admin_tapi as
  procedure save_opening(p_id in out number, p_expected_version in number, p_name in varchar2, p_opening_type in varchar2, p_description in clob, p_parent_opening_id in number, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    chess_validation_api.validate_opening(p_id,p_parent_opening_id);
    if p_id is null
    then
      insert into chess_opening (name, opening_type, description, parent_opening_id)
      values (p_name, p_opening_type, p_description, p_parent_opening_id) returning opening_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_opening where opening_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_opening set name=p_name, opening_type=p_opening_type, description=p_description, parent_opening_id=p_parent_opening_id, row_version=row_version+1
      where opening_id=p_id returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_opening_with_eco(p_id in out number, p_expected_version in number, p_name in varchar2, p_opening_type in varchar2, p_description in clob, p_parent_opening_id in number, p_eco_codes in varchar2, p_new_version out number) is
    l_code varchar2(3);
    l_count number;
    l_seen varchar2(32767) := ':';
    l_pos pls_integer := 1;
    l_end pls_integer;
  begin
    savepoint chess_opening_and_eco;
    -- Validate the complete set before changing either the opening or its links.
    if p_eco_codes is not null then
      if not regexp_like(p_eco_codes, '^[A-E][0-9][0-9](:[A-E][0-9][0-9])*$', 'c') then
        raise_application_error(-20014, 'Invalid ECO code selection.');
      end if;
      loop
        l_end := instr(p_eco_codes, ':', l_pos);
        if l_end = 0 then l_end := length(p_eco_codes) + 1; end if;
        l_code := substr(p_eco_codes, l_pos, l_end - l_pos);
        if instr(l_seen, ':' || l_code || ':') > 0 then
          raise_application_error(-20009, 'Duplicate ECO code selection.');
        end if;
        select count(*) into l_count from chess_eco_code where eco_code = l_code;
        if l_count = 0 then
          raise_application_error(-20013, 'A selected ECO code does not exist.');
        end if;
        l_seen := l_seen || l_code || ':';
        exit when l_end > length(p_eco_codes);
        l_pos := l_end + 1;
      end loop;
    end if;
    save_opening(p_id,p_expected_version,p_name,p_opening_type,p_description,p_parent_opening_id,p_new_version);
    delete from chess_opening_eco
     where opening_id = p_id and instr(l_seen, ':' || eco_code || ':') = 0;
    l_pos := 1;
    while l_pos < length(l_seen) loop
      l_end := instr(l_seen, ':', l_pos + 1);
      l_code := substr(l_seen, l_pos + 1, l_end - l_pos - 1);
      insert into chess_opening_eco (opening_id, eco_code)
      select p_id, l_code from dual
       where not exists (select 1 from chess_opening_eco where opening_id = p_id and eco_code = l_code);
      l_pos := l_end;
    end loop;
  exception
    when others then
      rollback to chess_opening_and_eco;
      raise;
  end;
  procedure delete_opening(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_opening where opening_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    delete from chess_opening where opening_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_gambit(p_id in out number, p_expected_version in number, p_name in varchar2, p_description in clob, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    if p_id is null
    then
      insert into chess_gambit (name, description)
      values (p_name, p_description) returning gambit_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_gambit where gambit_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_gambit set name=p_name, description=p_description, row_version=row_version+1
      where gambit_id=p_id returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure delete_gambit(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_gambit where gambit_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    delete from chess_gambit where gambit_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_concept(p_id in out number, p_expected_version in number, p_concept_code in varchar2, p_name in varchar2, p_category_code in varchar2, p_description in clob, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    if p_id is null
    then
      insert into chess_concept (concept_code, name, category_code, description)
      values (p_concept_code, p_name, p_category_code, p_description) returning concept_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_concept where concept_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_concept set concept_code=p_concept_code, name=p_name, category_code=p_category_code, description=p_description, row_version=row_version+1
      where concept_id=p_id returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure delete_concept(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_concept where concept_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    delete from chess_concept where concept_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_video(p_id in out number, p_expected_version in number, p_platform in varchar2, p_external_video_id in varchar2, p_video_url in varchar2, p_title in varchar2, p_creator in varchar2, p_description in clob, p_duration_seconds in number, p_published_on in date, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    chess_validation_api.validate_url(p_video_url);
    if p_id is null
    then
      insert into chess_video (platform, external_video_id, video_url, title, creator, description, duration_seconds, published_on)
      values (p_platform, p_external_video_id, p_video_url, p_title, p_creator, p_description, p_duration_seconds, p_published_on) returning video_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_video where video_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_video set platform=p_platform, external_video_id=p_external_video_id, video_url=p_video_url, title=p_title, creator=p_creator, description=p_description, duration_seconds=p_duration_seconds, published_on=p_published_on, updated_on=systimestamp, row_version=row_version+1
      where video_id=p_id returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure delete_video(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_video where video_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    delete from chess_video where video_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_commentary(p_id in out number, p_expected_version in number, p_opening_id in number, p_gambit_id in number, p_variation_id in number, p_commentary_kind in varchar2, p_title in varchar2, p_content in clob, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    if p_id is null
    then
      insert into chess_commentary (opening_id, gambit_id, variation_id, commentary_kind, title, content)
      values (p_opening_id, p_gambit_id, p_variation_id, p_commentary_kind, p_title, p_content) returning commentary_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_commentary where commentary_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_commentary set opening_id=p_opening_id, gambit_id=p_gambit_id, variation_id=p_variation_id, commentary_kind=p_commentary_kind, title=p_title, content=p_content, row_version=row_version+1
      where commentary_id=p_id returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure delete_commentary(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_commentary where commentary_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    delete from chess_commentary where commentary_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_game(p_id in out number, p_expected_version in number, p_white_player in varchar2, p_black_player in varchar2, p_event_name in varchar2, p_site in varchar2, p_game_date in date, p_result_code in varchar2, p_eco_code in varchar2, p_opening_id in number, p_pgn in clob, p_source_url in varchar2, p_commentary in clob, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    chess_validation_api.validate_pgn(p_pgn, false);
    chess_validation_api.validate_url(p_source_url);
    if p_id is null
    then
      insert into chess_game (white_player, black_player, event_name, site, game_date, result_code, eco_code, opening_id, pgn, source_url, commentary)
      values (p_white_player, p_black_player, p_event_name, p_site, p_game_date, p_result_code, p_eco_code, p_opening_id, p_pgn, p_source_url, p_commentary) returning game_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_game where game_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_game set white_player=p_white_player, black_player=p_black_player, event_name=p_event_name, site=p_site, game_date=p_game_date, result_code=p_result_code, eco_code=p_eco_code, opening_id=p_opening_id, pgn=p_pgn, source_url=p_source_url, commentary=p_commentary, row_version=row_version+1
      where game_id=p_id returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure delete_game(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_game where game_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    delete from chess_game where game_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_variation(p_id in out number, p_expected_version in number, p_opening_id in number, p_gambit_id in number, p_parent_variation_id in number, p_branch_ply in number, p_name in varchar2, p_line_kind in varchar2, p_pgn in clob, p_starting_fen in varchar2, p_annotation in clob, p_new_version out number) is
    l_version number;
    l_fen varchar2(200);
    l_parent clob;
    l_count number;
    l_opening_id number;
    l_gambit_id number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    if p_id is not null
    then
      select opening_id,gambit_id into l_opening_id,l_gambit_id
      from chess_variation where variation_id=p_id for update;
      if nvl(l_opening_id,-1)<>nvl(p_opening_id,-1)
         or nvl(l_gambit_id,-1)<>nvl(p_gambit_id,-1)
      then
        raise_application_error(-20022,'Ordinary maintenance cannot change variation ownership.');
      end if;
    end if;
    if (p_opening_id is null and p_gambit_id is null) or (p_opening_id is not null and p_gambit_id is not null)
    then
      raise_application_error(-20022,'Choose exactly one owner opening or gambit.');
    end if;
    if p_opening_id is not null
    then
      select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    else
      select row_version into l_version from chess_gambit where gambit_id=p_gambit_id for update;
    end if;
    if p_parent_variation_id is not null
    then
      if p_starting_fen is not null
      then
        raise_application_error(-20023,'Only a root variation may define a starting FEN.');
      end if;
      select count(*) into l_count from (
        select variation_id from chess_variation start with variation_id=p_parent_variation_id
        connect by nocycle prior parent_variation_id=variation_id
      ) where variation_id=p_id;
      if l_count>0
      then
        raise_application_error(-20024,'A variation cannot contain a hierarchy cycle.');
      end if;
      select pgn into l_parent from chess_variation where variation_id=p_parent_variation_id
        and (opening_id=p_opening_id or gambit_id=p_gambit_id) for update;
      select starting_fen into l_fen from chess_variation where parent_variation_id is null
        start with variation_id=p_parent_variation_id connect by nocycle prior parent_variation_id=variation_id;
      chess_validation_api.validate_branch(l_parent,p_pgn,p_branch_ply,l_fen);
    else
      l_fen := p_starting_fen;
    end if;
    chess_validation_api.validate_pgn(p_pgn,true,l_fen);
    if p_id is null
    then
      insert into chess_variation (opening_id, gambit_id, parent_variation_id, branch_ply, name, line_kind, pgn, starting_fen, annotation)
      values (p_opening_id, p_gambit_id, p_parent_variation_id, p_branch_ply, p_name, p_line_kind, p_pgn, p_starting_fen, p_annotation) returning variation_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_variation where variation_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_variation set opening_id=p_opening_id, gambit_id=p_gambit_id, parent_variation_id=p_parent_variation_id, branch_ply=p_branch_ply, name=p_name, line_kind=p_line_kind, pgn=p_pgn, starting_fen=p_starting_fen, annotation=p_annotation, row_version=row_version+1
      where variation_id=p_id returning row_version into p_new_version;
    end if;
    chess_validation_api.validate_variation_tree(p_id);
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure delete_variation(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_variation where variation_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    delete from chess_variation where variation_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_image(p_id in out number, p_expected_version in number, p_filename in varchar2, p_mime_type in varchar2, p_description in varchar2, p_accessibility_text in varchar2, p_image_content in blob, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    if p_id is null or p_image_content is not null
    then
      chess_validation_api.validate_image(p_image_content,p_mime_type,p_accessibility_text);
    elsif trim(p_accessibility_text) is null
    then
      raise_application_error(-20005, 'Image alternative text is required.');
    end if;
    if p_id is null
    then
      insert into chess_image (filename, mime_type, description, accessibility_text, image_content)
      values (p_filename, p_mime_type, p_description, p_accessibility_text, p_image_content) returning image_id,row_version into p_id,p_new_version;
    else
      select row_version into l_version from chess_image where image_id=p_id for update;
      chess_validation_api.require_version(l_version,p_expected_version);
      update chess_image set filename=p_filename, mime_type=case when p_image_content is null then mime_type else p_mime_type end, description=p_description, accessibility_text=p_accessibility_text, image_content=case when p_image_content is null then image_content else p_image_content end, row_version=row_version+1
      where image_id=p_id returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A record with these details already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure delete_image(p_id number, p_expected_version number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_image where image_id=p_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    update chess_opening set row_version=row_version+1 where opening_id in
      (select opening_id from chess_image_opening where image_id=p_id);
    update chess_gambit set row_version=row_version+1 where gambit_id in
      (select gambit_id from chess_image_gambit where image_id=p_id);
    update chess_variation set row_version=row_version+1 where variation_id in
      (select variation_id from chess_image_variation where image_id=p_id);
    delete from chess_image_opening where image_id=p_id;
    delete from chess_image_gambit where image_id=p_id;
    delete from chess_image_variation where image_id=p_id;
    delete from chess_image where image_id=p_id;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Record does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode=-2292
      then
        raise_application_error(-20010, 'This record is still referenced. Remove its links first.');
      end if;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_opening_gambit(p_opening_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_gambit where gambit_id=p_gambit_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_opening_gambit (opening_id,gambit_id) values (p_opening_id,p_gambit_id);
    else
      delete from chess_opening_gambit where opening_id=p_opening_id and gambit_id=p_gambit_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_opening set row_version=row_version+1 where opening_id=p_opening_id returning row_version into p_new_version;
    update chess_gambit set row_version=row_version+1 where gambit_id=p_gambit_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_concept_opening(p_concept_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_concept where concept_id=p_concept_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_concept_opening (concept_id,opening_id) values (p_concept_id,p_opening_id);
    else
      delete from chess_concept_opening where concept_id=p_concept_id and opening_id=p_opening_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_concept set row_version=row_version+1 where concept_id=p_concept_id returning row_version into p_new_version;
    update chess_opening set row_version=row_version+1 where opening_id=p_opening_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_concept_gambit(p_concept_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_concept where concept_id=p_concept_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_gambit where gambit_id=p_gambit_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_concept_gambit (concept_id,gambit_id) values (p_concept_id,p_gambit_id);
    else
      delete from chess_concept_gambit where concept_id=p_concept_id and gambit_id=p_gambit_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_concept set row_version=row_version+1 where concept_id=p_concept_id returning row_version into p_new_version;
    update chess_gambit set row_version=row_version+1 where gambit_id=p_gambit_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_concept_variation(p_concept_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_concept where concept_id=p_concept_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_variation where variation_id=p_variation_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_concept_variation (concept_id,variation_id) values (p_concept_id,p_variation_id);
    else
      delete from chess_concept_variation where concept_id=p_concept_id and variation_id=p_variation_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_concept set row_version=row_version+1 where concept_id=p_concept_id returning row_version into p_new_version;
    update chess_variation set row_version=row_version+1 where variation_id=p_variation_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_video_opening(p_video_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_video where video_id=p_video_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_video_opening (video_id,opening_id) values (p_video_id,p_opening_id);
    else
      delete from chess_video_opening where video_id=p_video_id and opening_id=p_opening_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_video set row_version=row_version+1, updated_on=systimestamp where video_id=p_video_id returning row_version into p_new_version;
    update chess_opening set row_version=row_version+1 where opening_id=p_opening_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_video_gambit(p_video_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_video where video_id=p_video_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_gambit where gambit_id=p_gambit_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_video_gambit (video_id,gambit_id) values (p_video_id,p_gambit_id);
    else
      delete from chess_video_gambit where video_id=p_video_id and gambit_id=p_gambit_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_video set row_version=row_version+1, updated_on=systimestamp where video_id=p_video_id returning row_version into p_new_version;
    update chess_gambit set row_version=row_version+1 where gambit_id=p_gambit_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_video_variation(p_video_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_video where video_id=p_video_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_variation where variation_id=p_variation_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_video_variation (video_id,variation_id) values (p_video_id,p_variation_id);
    else
      delete from chess_video_variation where video_id=p_video_id and variation_id=p_variation_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_video set row_version=row_version+1, updated_on=systimestamp where video_id=p_video_id returning row_version into p_new_version;
    update chess_variation set row_version=row_version+1 where variation_id=p_variation_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_image_opening(p_image_id number, p_opening_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_image where image_id=p_image_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_image_opening (image_id,opening_id) values (p_image_id,p_opening_id);
    else
      delete from chess_image_opening where image_id=p_image_id and opening_id=p_opening_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_image set row_version=row_version+1 where image_id=p_image_id returning row_version into p_new_version;
    update chess_opening set row_version=row_version+1 where opening_id=p_opening_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_image_gambit(p_image_id number, p_gambit_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_image where image_id=p_image_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_gambit where gambit_id=p_gambit_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_image_gambit (image_id,gambit_id) values (p_image_id,p_gambit_id);
    else
      delete from chess_image_gambit where image_id=p_image_id and gambit_id=p_gambit_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_image set row_version=row_version+1 where image_id=p_image_id returning row_version into p_new_version;
    update chess_gambit set row_version=row_version+1 where gambit_id=p_gambit_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_image_variation(p_image_id number, p_variation_id number, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_image where image_id=p_image_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    select row_version into l_version from chess_variation where variation_id=p_variation_id for update;
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_image_variation (image_id,variation_id) values (p_image_id,p_variation_id);
    else
      delete from chess_image_variation where image_id=p_image_id and variation_id=p_variation_id;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_image set row_version=row_version+1 where image_id=p_image_id returning row_version into p_new_version;
    update chess_variation set row_version=row_version+1 where variation_id=p_variation_id;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_opening_eco(p_opening_id number, p_eco_code varchar2, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_opening_eco (opening_id,eco_code) values (p_opening_id,p_eco_code);
    else
      delete from chess_opening_eco where opening_id=p_opening_id and eco_code=p_eco_code;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_opening set row_version=row_version+1 where opening_id=p_opening_id returning row_version into p_new_version;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure link_opening_alias(p_opening_id number, p_alias_name varchar2, p_expected_version number, p_link boolean, p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    if p_link is null
    then
      raise_application_error(-20011, 'Choose link or unlink.');
    elsif p_link
    then
      insert into chess_opening_alias (opening_id,alias_name) values (p_opening_id,p_alias_name);
    else
      delete from chess_opening_alias where opening_id=p_opening_id and alias_name=p_alias_name;
      if sql%rowcount=0
      then
        raise_application_error(-20012, 'The link does not exist.');
      end if;
    end if;
    update chess_opening set row_version=row_version+1 where opening_id=p_opening_id returning row_version into p_new_version;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009, 'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;

  procedure link_gambit_opening(p_gambit_id number,p_opening_id number,p_expected_version number,p_link boolean,p_new_version out number) is
    l_version number;
  begin
    savepoint chess_admin_link;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_opening where opening_id=p_opening_id for update;
    select row_version into l_version from chess_gambit where gambit_id=p_gambit_id for update;
    chess_validation_api.require_version(l_version,p_expected_version);
    if p_link is null then
      raise_application_error(-20011,'Choose link or unlink.');
    elsif p_link then
      insert into chess_opening_gambit (opening_id,gambit_id) values (p_opening_id,p_gambit_id);
    else
      delete from chess_opening_gambit where opening_id=p_opening_id and gambit_id=p_gambit_id;
      if sql%rowcount=0 then raise_application_error(-20012,'The link does not exist.'); end if;
    end if;
    update chess_opening set row_version=row_version+1 where opening_id=p_opening_id;
    update chess_gambit set row_version=row_version+1 where gambit_id=p_gambit_id returning row_version into p_new_version;
  exception
    when no_data_found then
      rollback to chess_admin_link;
      raise_application_error(-20008,'A linked record does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_link;
      raise_application_error(-20009,'This link already exists.');
    when others then
      rollback to chess_admin_link;
      if sqlcode=-2291 then
        raise_application_error(-20013,'A selected related record does not exist.');
      elsif sqlcode=-2290 then
        raise_application_error(-20014,'A value violates its allowed category, ownership or format.');
      elsif sqlcode=-12899 then
        raise_application_error(-20016,'A value is longer than the allowed field length.');
      elsif sqlcode=-1400 then
        raise_application_error(-20015,'A required value is missing.');
      end if;
      raise;
  end;
  procedure save_content_source(
    p_original_creator in varchar2, p_expected_version in number,
    p_creator in varchar2, p_author in varchar2, p_notes in clob,
    p_new_version out number) is
    l_version number;
    l_references number;
  begin
    savepoint chess_admin_save;
    chess_validation_api.lock_control;
    if trim(p_creator) is null then
      raise_application_error(-20015, 'Creator or Publisher is required.');
    end if;
    if p_original_creator is null then
      insert into chess_content_source (creator, author, notes)
      values (p_creator, p_author, p_notes)
      returning row_version into p_new_version;
    else
      select row_version into l_version from chess_content_source
      where creator = p_original_creator for update;
      chess_validation_api.require_version(l_version, p_expected_version);
      if p_creator != p_original_creator then
        select count(*) into l_references from chess_video
        where creator = p_original_creator;
        if l_references > 0 then
          raise_application_error(-20010,
            'This creator is used by videos. Create a replacement and reassign the videos before renaming.');
        end if;
      end if;
      update chess_content_source
      set creator = p_creator, author = p_author, notes = p_notes,
          updated_on = systimestamp, row_version = row_version + 1
      where creator = p_original_creator
      returning row_version into p_new_version;
    end if;
  exception
    when no_data_found then
      rollback to chess_admin_save;
      raise_application_error(-20008, 'Content source does not exist.');
    when dup_val_on_index then
      rollback to chess_admin_save;
      raise_application_error(-20009, 'A content source with this creator already exists.');
    when others then
      rollback to chess_admin_save;
      if sqlcode = -2292 then
        raise_application_error(-20010,
          'This creator is used by videos. Create a replacement and reassign the videos before renaming.');
      elsif sqlcode = -12899 then
        raise_application_error(-20016, 'Creator and Author must each be at most 300 characters.');
      elsif sqlcode = -1400 then
        raise_application_error(-20015, 'Creator or Publisher is required.');
      end if;
      raise;
  end save_content_source;

  procedure delete_content_source(p_creator in varchar2, p_expected_version in number) is
    l_version number;
  begin
    savepoint chess_admin_delete;
    chess_validation_api.lock_control;
    select row_version into l_version from chess_content_source
    where creator = p_creator for update;
    chess_validation_api.require_version(l_version, p_expected_version);
    delete from chess_content_source where creator = p_creator;
  exception
    when no_data_found then
      rollback to chess_admin_delete;
      raise_application_error(-20008, 'Content source does not exist.');
    when others then
      rollback to chess_admin_delete;
      if sqlcode = -2292 then
        raise_application_error(-20010,
          'This creator is used by videos. Reassign the videos before deleting the source.');
      end if;
      raise;
  end delete_content_source;
  -- Lock control serialises aggregate mutations before checking both observed versions.
  procedure set_subject_video_link(p_subject_type in varchar2, p_subject_id in number, p_expected_subject_version in number, p_video_id in number, p_expected_video_version in number, p_link in boolean, p_new_subject_version out number, p_new_video_version out number) is
    l_subject_version number;
    l_video_version number;
  begin
    savepoint chess_subject_video_link;
    chess_validation_api.lock_control;
    if p_subject_type = 'OPENING'
    then
      select row_version into l_subject_version from chess_opening where opening_id=p_subject_id for update;
    elsif p_subject_type = 'GAMBIT'
    then
      select row_version into l_subject_version from chess_gambit where gambit_id=p_subject_id for update;
    else
      raise_application_error(-20014, 'Choose an opening or gambit.');
    end if;
    chess_validation_api.require_version(l_subject_version,p_expected_subject_version);
    select row_version into l_video_version from chess_video where video_id=p_video_id for update;
    chess_validation_api.require_version(l_video_version,p_expected_video_version);
    if p_subject_type = 'OPENING'
    then
      link_video_opening(p_video_id,p_subject_id,p_expected_video_version,p_link,p_new_video_version);
    else
      link_video_gambit(p_video_id,p_subject_id,p_expected_video_version,p_link,p_new_video_version);
    end if;
    -- Existing link routines increment each aggregate once under the control lock.
    p_new_subject_version := l_subject_version + 1;
  exception
    when no_data_found then
      rollback to chess_subject_video_link;
      raise_application_error(-20008, 'A linked record does not exist.');
    when others then
      rollback to chess_subject_video_link;
      raise;
  end set_subject_video_link;

  procedure create_video_for_subject(p_platform in varchar2, p_external_video_id in varchar2, p_video_url in varchar2, p_title in varchar2, p_creator in varchar2, p_description in clob, p_duration_seconds in number, p_published_on in date, p_subject_type in varchar2, p_subject_id in number, p_expected_subject_version in number, p_video_id out number, p_new_subject_version out number, p_new_video_version out number) is
    l_video_id number;
    l_video_version number;
  begin
    savepoint chess_subject_video_create;
    chess_validation_api.lock_control;
    save_video(l_video_id,null,p_platform,p_external_video_id,p_video_url,p_title,p_creator,p_description,p_duration_seconds,p_published_on,l_video_version);
    set_subject_video_link(p_subject_type,p_subject_id,p_expected_subject_version,l_video_id,l_video_version,true,p_new_subject_version,p_new_video_version);
    p_video_id := l_video_id;
  exception
    when others then
      rollback to chess_subject_video_create;
      raise;
  end create_video_for_subject;
end chess_admin_tapi;
/
--rollback drop package body orac_chess.chess_admin_tapi;
