--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_content_source annotations (add if not exists display_name 'Chess content sources');
--rollback alter table orac_chess.chess_content_source annotations (drop display_name);

--changeset clive:orac_chess_content_source_creator_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_content_source modify creator annotations (add if not exists display_name 'Creator or Publisher', add if not exists semantic_role 'primary_key', add if not exists data_kind 'identifier');
--rollback alter table orac_chess.chess_content_source modify creator annotations (drop display_name, drop semantic_role, drop data_kind);

--changeset clive:orac_chess_content_source_author_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_content_source modify author annotations (add if not exists display_name 'Author', add if not exists semantic_role 'dimension', add if not exists data_kind 'text');
--rollback alter table orac_chess.chess_content_source modify author annotations (drop display_name, drop semantic_role, drop data_kind);

--changeset clive:orac_chess_content_source_notes_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_content_source modify notes annotations (add if not exists display_name 'Notes', add if not exists semantic_role 'payload', add if not exists data_kind 'text');
--rollback alter table orac_chess.chess_content_source modify notes annotations (drop display_name, drop semantic_role, drop data_kind);

--changeset clive:orac_chess_content_source_created_on_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_content_source modify created_on annotations (add if not exists display_name 'Created on', add if not exists semantic_role 'audit', add if not exists data_kind 'datetime');
--rollback alter table orac_chess.chess_content_source modify created_on annotations (drop display_name, drop semantic_role, drop data_kind);

--changeset clive:orac_chess_content_source_updated_on_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_content_source modify updated_on annotations (add if not exists display_name 'Updated on', add if not exists semantic_role 'audit', add if not exists data_kind 'datetime');
--rollback alter table orac_chess.chess_content_source modify updated_on annotations (drop display_name, drop semantic_role, drop data_kind);

--changeset clive:orac_chess_content_source_row_version_annotation context:plugin,prod labels:plugin stripComments:false runOnChange:true
alter table orac_chess.chess_content_source modify row_version annotations (add if not exists display_name 'Optimistic version', add if not exists semantic_role 'audit', add if not exists data_kind 'quantity');
--rollback alter table orac_chess.chess_content_source modify row_version annotations (drop display_name, drop semantic_role, drop data_kind);
