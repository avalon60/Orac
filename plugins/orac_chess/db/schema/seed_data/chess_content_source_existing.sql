--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_existing context:plugin,prod labels:plugin stripComments:false
merge into orac_chess.chess_content_source target
using (select distinct creator from orac_chess.chess_video where creator is not null) source
on (target.creator = source.creator)
when not matched then insert (creator) values (source.creator);
-- Preserve existing video creators; never delete videos during rollback.
--rollback empty
