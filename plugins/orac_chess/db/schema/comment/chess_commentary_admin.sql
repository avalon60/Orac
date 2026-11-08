--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Documents technical Chess administration metadata.
-- Purpose: Record approved concurrency and persisted configuration semantics.
-- Usage: Managed plugin metadata controller after additive structure migration.

--changeset clive:orac_chess_admin_chess_commentary_version_comment context:plugin,prod labels:plugin runOnChange:true stripComments:false
comment on column orac_chess.chess_commentary.row_version is 'Optimistic concurrency token, initially 1; controlled successful mutations advance the token and callers supply their observed value.';
--rollback comment on column orac_chess.chess_commentary.row_version is '';
