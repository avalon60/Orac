--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_video and its columns.
-- Purpose: Install the comment object chess_video in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_video context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_video is 'External instructional video reference and descriptive metadata only.';
comment on column orac_chess.chess_video.video_id is 'Video id for chess video.';
comment on column orac_chess.chess_video.platform is 'Platform for chess video.';
comment on column orac_chess.chess_video.external_video_id is 'External video id for chess video.';
comment on column orac_chess.chess_video.video_url is 'Video url for chess video.';
comment on column orac_chess.chess_video.title is 'Title for chess video.';
comment on column orac_chess.chess_video.creator is 'Creator for chess video.';
comment on column orac_chess.chess_video.description is 'Description for chess video.';
comment on column orac_chess.chess_video.duration_seconds is 'Duration seconds for chess video.';
comment on column orac_chess.chess_video.published_on is 'Published on for chess video.';
comment on column orac_chess.chess_video.created_on is 'Created on for chess video.';
comment on column orac_chess.chess_video.updated_on is 'Modification time; future writing application must set this on update.';

--rollback comment on table orac_chess.chess_video is '';
--rollback comment on column orac_chess.chess_video.video_id is '';
--rollback comment on column orac_chess.chess_video.platform is '';
--rollback comment on column orac_chess.chess_video.external_video_id is '';
--rollback comment on column orac_chess.chess_video.video_url is '';
--rollback comment on column orac_chess.chess_video.title is '';
--rollback comment on column orac_chess.chess_video.creator is '';
--rollback comment on column orac_chess.chess_video.description is '';
--rollback comment on column orac_chess.chess_video.duration_seconds is '';
--rollback comment on column orac_chess.chess_video.published_on is '';
--rollback comment on column orac_chess.chess_video.created_on is '';
--rollback comment on column orac_chess.chess_video.updated_on is '';
