--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Grant only read on the separate Chess query projection.
-- Purpose: Allow the Core query executor to read this view.
-- Usage: Plugin installation and upgrade lifecycle.

--changeset clive:orac_chess_query_eco_code_read context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant read on orac_chess.chess_query_eco_code_v to orac_plugin;
--rollback revoke read on orac_chess.chess_query_eco_code_v from orac_plugin;
