--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_seed context:plugin,prod labels:plugin stripComments:false
merge into orac_chess.chess_content_source target
using (
  select 'ChessVibes' creator, 'Nelson Lopez' author, 'NM' notes from dual
  union all
  select 'Square One Chess' creator, 'squareonechess6939' author, 'Pundit' notes from dual
  union all
  select 'Remote Chess Academy' creator, 'Igor Smirnov' author, 'GM' notes from dual
  union all
  select 'ChesswithAkeem' creator, 'Akeem Brown' author, 'CM' notes from dual
  union all
  select 'ChessCenturion' creator, 'Alex' author, '~2000' notes from dual
) source
on (target.creator = source.creator)
when not matched then insert (creator, author, notes)
values (source.creator, source.author, source.notes);
-- Preserve user-edited and referenced source rows; table rollback owns removal.
--rollback empty
