--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_comments context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_eco_code is 'ECO reference: all distinct upstream English opening names per code, sorted and newline-separated.';
comment on column orac_chess.chess_eco_code.eco_code is 'Encyclopaedia of Chess Openings code A00 to E99.';
comment on column orac_chess.chess_eco_code.description is 'Distinct English source opening names; not a single canonical ECO title.';
--rollback comment on table orac_chess.chess_eco_code is '';
--rollback comment on column orac_chess.chess_eco_code.eco_code is '';
--rollback comment on column orac_chess.chess_eco_code.description is '';
