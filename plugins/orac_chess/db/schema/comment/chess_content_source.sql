--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_comment_table context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_content_source is 'Content creators and publishers used by Chess instructional videos.';
--rollback comment on table orac_chess.chess_content_source is '';

--changeset clive:orac_chess_content_source_comment_creator context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on column orac_chess.chess_content_source.creator is 'Creator or publisher identity; natural primary key.';
--rollback comment on column orac_chess.chess_content_source.creator is '';

--changeset clive:orac_chess_content_source_comment_author context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on column orac_chess.chess_content_source.author is 'Person or account associated with the creator.';
--rollback comment on column orac_chess.chess_content_source.author is '';

--changeset clive:orac_chess_content_source_comment_notes context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on column orac_chess.chess_content_source.notes is 'Editable credentials or other source notes.';
--rollback comment on column orac_chess.chess_content_source.notes is '';

--changeset clive:orac_chess_content_source_comment_created_on context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on column orac_chess.chess_content_source.created_on is 'Creation timestamp.';
--rollback comment on column orac_chess.chess_content_source.created_on is '';

--changeset clive:orac_chess_content_source_comment_updated_on context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on column orac_chess.chess_content_source.updated_on is 'Last change timestamp.';
--rollback comment on column orac_chess.chess_content_source.updated_on is '';

--changeset clive:orac_chess_content_source_comment_row_version context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on column orac_chess.chess_content_source.row_version is 'Optimistic concurrency version.';
--rollback comment on column orac_chess.chess_content_source.row_version is '';

