--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Documents technical Chess administration metadata.
-- Purpose: Record approved concurrency and persisted configuration semantics.
-- Usage: Managed plugin metadata controller after additive structure migration.

--changeset clive:orac_chess_admin_chess_video_version_annotation context:plugin,prod labels:plugin runOnChange:true stripComments:false
alter table orac_chess.chess_video modify row_version annotations (add if not exists display_name 'Optimistic version', add if not exists semantic_role 'audit', add if not exists data_kind 'quantity');
--rollback alter table orac_chess.chess_video modify row_version annotations (drop display_name, drop semantic_role, drop data_kind);

--changeset clive:orac_chess_content_source_video_creator_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_video modify creator annotations (add if not exists display_name 'Creator or Publisher', add if not exists semantic_role 'foreign_key', add if not exists data_kind 'identifier', add if not exists rel_target 'orac_chess.chess_content_source.creator', add if not exists rel_type 'references', add if not exists rel_cardinality 'many_to_one', add if not exists rel_optionality 'optional', add if not exists rel_basis 'constraint:chs_vid_creator_fk');
--rollback alter table orac_chess.chess_video modify creator annotations (drop display_name, drop semantic_role, drop data_kind, drop rel_target, drop rel_type, drop rel_cardinality, drop rel_optionality, drop rel_basis);
