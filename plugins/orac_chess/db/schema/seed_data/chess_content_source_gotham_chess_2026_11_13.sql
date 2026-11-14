--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Nov-2026
-- Description: Adds Gotham Chess to Chess content source reference data.
-- Purpose: Supply the publisher and author while preserving existing source edits.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_gotham_chess_2026_11_13 context:plugin,prod labels:plugin stripComments:false
merge into orac_chess.chess_content_source target
using (
  select 'Gotham Chess' creator, 'Levy Rozman' author, null notes from dual
) source
on (target.creator = source.creator)
when not matched then insert (creator, author, notes)
values (source.creator, source.author, source.notes);
-- Preserve user-edited and referenced source rows; table rollback owns removal.
--rollback empty
