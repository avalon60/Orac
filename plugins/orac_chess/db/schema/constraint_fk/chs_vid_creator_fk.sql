--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_video_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_VID_CREATOR_FK'
alter table orac_chess.chess_video add constraint chs_vid_creator_fk foreign key (creator) references orac_chess.chess_content_source (creator);
--rollback alter table orac_chess.chess_video drop constraint chs_vid_creator_fk;
