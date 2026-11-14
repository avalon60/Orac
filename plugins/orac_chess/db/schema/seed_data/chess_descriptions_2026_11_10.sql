--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 10-Nov-2026
-- Description: Reset the authorised Vienna test subject and fill one missing video description.
-- Purpose: Restore canonical Vienna subject fields/ECO and preserve other maintained descriptions.
-- Usage: Managed plugin install/upgrade through db/liquibase/pluginController.xml.
--changeset clive:orac_chess_descriptions_2026_11_10 context:plugin,prod labels:plugin stripComments:false endDelimiter:/
declare
  l_opening orac_chess.chess_opening_v%rowtype;
  l_video orac_chess.chess_video_v%rowtype;
  l_next number;
  l_eco_count number;
  l_canonical_eco_count number;

  function blank(p_value clob) return boolean is
  begin
    return p_value is null or dbms_lob.getlength(p_value) = 0
      or not regexp_like(p_value,'[^[:space:]]');
  end;
begin
  savepoint chess_description_backfill;
  begin
    select opening_id,name,opening_type,description,parent_opening_id,row_version
    into l_opening from orac_chess.chess_opening_v where name = 'Vienna Game';
  exception
    when no_data_found then
      l_opening.opening_id := null; -- Preserve deliberate deletions.
  end;
  if l_opening.opening_id is not null
  then
    select count(*),count(case when eco_code = 'C25' then 1 end)
    into l_eco_count,l_canonical_eco_count from orac_chess.chess_opening_eco_v
    where opening_id = l_opening.opening_id;
    -- Explicit user-authorised reset of pre-bootstrap Vienna test fields only.
    -- Existing canonical root/branches already match the seed; retain their IDs/versions.
    if l_opening.opening_type != 'OPENING' or l_opening.parent_opening_id is not null
      or nvl(dbms_lob.compare(l_opening.description,
        to_clob('White develops Nc3 before Nf3, retaining the option of an early f-pawn advance.')),1) != 0
      or l_eco_count != 1 or l_canonical_eco_count != 1
    then
      orac_chess.chess_admin_api.save_opening_with_eco(l_opening.opening_id,l_opening.row_version,
        'Vienna Game','OPENING',
        to_clob('White develops Nc3 before Nf3, retaining the option of an early f-pawn advance.'),
        null,'C25',l_next);
    end if;
  end if;
  begin
    select video_id,platform,external_video_id,video_url,title,creator,description,
      duration_seconds,published_on,created_on,updated_on,row_version
    into l_video from orac_chess.chess_video_v
    where platform = 'YouTube' and external_video_id = '0ehLrDd2pn4';
  exception
    when no_data_found then
      l_video.video_id := null; -- Preserve deliberate deletions.
  end;
  if l_video.video_id is not null and blank(l_video.description)
  then
    orac_chess.chess_admin_api.save_video(l_video.video_id,l_video.row_version,
      l_video.platform,l_video.external_video_id,l_video.video_url,l_video.title,l_video.creator,
      to_clob('ChessVibes instructional video presenting four levels of the interference tactic.'),
      l_video.duration_seconds,l_video.published_on,l_next);
  end if;
exception
  when others then
    rollback to chess_description_backfill;
    raise;
end;
/
-- Descriptions and the authorised Vienna correction are retained on rollback.
--rollback empty
