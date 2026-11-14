--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 12-Nov-2026
-- Description: Bounded reviewed Chess explanation evidence.
-- Purpose: Expose only declared text and move context through a read-only view.
-- Usage: Included through the managed Chess plugin controller.

--changeset clive:orac_chess_chess_query_variation_line_v_read context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant read on orac_chess.chess_query_variation_line_v to orac_plugin;
--rollback revoke read on orac_chess.chess_query_variation_line_v from orac_plugin;
