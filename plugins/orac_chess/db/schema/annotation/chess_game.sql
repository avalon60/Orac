--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Documents technical Chess administration metadata.
-- Purpose: Record approved concurrency and persisted configuration semantics.
-- Usage: Managed plugin metadata controller after additive structure migration.

--changeset clive:orac_chess_admin_chess_game_version_annotation context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter table orac_chess.chess_game modify row_version annotations (add if not exists display_name 'Optimistic version', add if not exists semantic_role 'audit', add if not exists data_kind 'quantity');
--rollback alter table orac_chess.chess_game modify row_version annotations (drop display_name, drop semantic_role, drop data_kind);
