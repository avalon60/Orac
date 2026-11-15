--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 14-Nov-2026
-- Description: Adds missing top-26 YouTube chess content providers to the Chess source catalogue.
-- Purpose: Extend creator identities without duplicating providers in the existing source seeds.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.
-- Existing providers excluded: Gotham Chess, ChessVibes, Remote Chess Academy, ChesswithAkeem.

--changeset clive:orac_chess_content_source_top_26_gaps_2026_11_14 context:plugin,prod labels:plugin stripComments:false
merge into orac_chess.chess_content_source target
using (
  select 'GMHikaru' creator, 'Hikaru Nakamura' author, 'GM' notes from dual
  union all
  select 'BotezLive', 'Alexandra Botez and Andrea Botez', 'Alexandra: WFM' from dual
  union all
  select 'Anna Cramling', 'Anna Cramling', 'WFM' from dual
  union all
  select 'Magnus Carlsen', 'Magnus Carlsen', 'GM' from dual
  union all
  select 'agadmator''s Chess Channel', 'Antonio Radic', null from dual
  union all
  select 'Dina Belenkaya', 'Dina Belenkaya', 'WGM' from dual
  union all
  select 'Eric Rosen', 'Eric Rosen', 'IM' from dual
  union all
  select 'akaNemsko', 'Qiyu Zhou', 'FM' from dual
  union all
  select 'Chessbrah', 'Eric Hansen and Aman Hambleton', 'Both GM' from dual
  union all
  select 'ChessBase India', 'Sagar Shah and Amruta Mokal', 'Sagar: IM' from dual
  union all
  select 'Hanging Pawns', 'Stjepan Tomic', null from dual
  union all
  select 'ChessNetwork', 'Jerry', null from dual
  union all
  select 'the chess nerd', 'Zachary Saine', null from dual
  union all
  select 'Alex Banzea', 'Alexandru Banzea', 'IM' from dual
  union all
  select 'GMBenjaminFinegold', 'Benjamin Finegold', 'GM' from dual
  union all
  select 'John Bartholomew', 'John Bartholomew', 'IM' from dual
  union all
  select 'PowerPlayChess', 'Daniel King', 'GM' from dual
  union all
  select 'GingerGM', 'Simon Williams', 'GM' from dual
  union all
  select 'Chess Coach Andras', 'Andras Toth', 'FIDE Instructor' from dual
  union all
  select 'Kingscrusher', 'Tryfon Gavriel', 'CM' from dual
  union all
  select 'Mato Jelic', 'Mato Jelic', null from dual
  union all
  select 'Daniel Naroditsky', 'Daniel Naroditsky', 'GM' from dual
) source
on (target.creator = source.creator)
when not matched then insert (creator, author, notes)
values (source.creator, source.author, source.notes);
-- Preserve user-edited and referenced source rows; table rollback owns removal.
--rollback empty
