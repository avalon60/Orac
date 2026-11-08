--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_annotations context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_eco_code annotations (add if not exists display_name 'ECO codes');
alter table orac_chess.chess_eco_code modify eco_code annotations (add if not exists display_name 'ECO code', add if not exists semantic_role 'primary_key', add if not exists data_kind 'identifier');
alter table orac_chess.chess_eco_code modify description annotations (add if not exists display_name 'Opening names', add if not exists semantic_role 'payload', add if not exists data_kind 'text');
--rollback alter table orac_chess.chess_eco_code annotations (drop display_name);
--rollback alter table orac_chess.chess_eco_code modify eco_code annotations (drop display_name, drop semantic_role, drop data_kind);
--rollback alter table orac_chess.chess_eco_code modify description annotations (drop display_name, drop semantic_role, drop data_kind);
