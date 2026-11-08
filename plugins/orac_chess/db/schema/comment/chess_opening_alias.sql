--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_opening_alias and its columns.
-- Purpose: Install the comment object chess_opening_alias in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_opening_alias context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_opening_alias is 'Alternative recognised names for one opening.';
comment on column orac_chess.chess_opening_alias.opening_alias_id is 'Opening alias id for chess opening alias.';
comment on column orac_chess.chess_opening_alias.opening_id is 'Opening id for chess opening alias.';
comment on column orac_chess.chess_opening_alias.alias_name is 'Alias name for chess opening alias.';

--rollback comment on table orac_chess.chess_opening_alias is '';
--rollback comment on column orac_chess.chess_opening_alias.opening_alias_id is '';
--rollback comment on column orac_chess.chess_opening_alias.opening_id is '';
--rollback comment on column orac_chess.chess_opening_alias.alias_name is '';
