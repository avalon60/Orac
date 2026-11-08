--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_view context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_content_source_v as
select creator, author, notes, created_on, updated_on, row_version
from orac_chess.chess_content_source;
--rollback drop view orac_chess.chess_content_source_v;
