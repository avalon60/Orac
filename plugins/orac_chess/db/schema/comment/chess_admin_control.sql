--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Documents technical Chess administration metadata.
-- Purpose: Record approved concurrency and persisted configuration semantics.
-- Usage: Managed plugin metadata controller after additive structure migration.

--changeset clive:orac_chess_admin_control_comment context:plugin,prod labels:plugin runOnChange:true stripComments:false
comment on table orac_chess.chess_admin_control is 'Singleton persisted image upload limit and transaction lock shared by controlled Chess administration mutations.';
--rollback comment on table orac_chess.chess_admin_control is '';

--changeset clive:orac_chess_admin_control_id_comment context:plugin,prod labels:plugin runOnChange:true stripComments:false
comment on column orac_chess.chess_admin_control.control_id is 'The sole permitted key is 1; maintenance APIs lock this row until caller commit or rollback.';
--rollback comment on column orac_chess.chess_admin_control.control_id is '';

--changeset clive:orac_chess_admin_control_limit_comment context:plugin,prod labels:plugin runOnChange:true stripComments:false
comment on column orac_chess.chess_admin_control.max_image_bytes is 'Positive integer maximum PNG/JPEG upload size in bytes; default 10485760; changed only by an approved administrative operation.';
--rollback comment on column orac_chess.chess_admin_control.max_image_bytes is '';
