--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Documents technical Chess administration metadata.
-- Purpose: Record approved concurrency and persisted configuration semantics.
-- Usage: Managed plugin metadata controller after additive structure migration.

--changeset clive:orac_chess_admin_control_annotation context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter table orac_chess.chess_admin_control annotations (add if not exists display_name 'Chess administration control');
--rollback alter table orac_chess.chess_admin_control annotations (drop display_name);

--changeset clive:orac_chess_admin_control_key_annotation context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter table orac_chess.chess_admin_control modify control_id annotations (add if not exists display_name 'Singleton control identity', add if not exists semantic_role 'primary_key', add if not exists data_kind 'identifier');
--rollback alter table orac_chess.chess_admin_control modify control_id annotations (drop display_name, drop semantic_role, drop data_kind);

--changeset clive:orac_chess_admin_control_limit_annotation context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter table orac_chess.chess_admin_control modify max_image_bytes annotations (add if not exists display_name 'Maximum image bytes', add if not exists semantic_role 'measure', add if not exists data_kind 'quantity');
--rollback alter table orac_chess.chess_admin_control modify max_image_bytes annotations (drop display_name, drop semantic_role, drop data_kind);
