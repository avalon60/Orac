--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 11-Nov-2026
-- Description: Describe private source-management metadata.
-- Purpose: Document adoption protection, tombstones and source/applied snapshots.
-- Usage: Managed Chess plugin deployment.
--changeset clive:orac_chess_catalogue_entry_comments context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_catalogue_entry is 'Private catalogue identities and three-way source/applied/user-override baselines; not application reference data.';
comment on column orac_chess.chess_catalogue_entry.catalogue_key is 'Stable source identity independent of display name and source revision.';
comment on column orac_chess.chess_catalogue_entry.ownership is 'CREATED is source-managed; ADOPTED protects pre-existing subject fields and edges.';
comment on column orac_chess.chess_catalogue_entry.baseline_json is 'Previous source desired state, actual applied state, persistent user overrides and observed version.';
comment on column orac_chess.chess_catalogue_entry.last_source_hash is 'SHA-256 of canonical desired fields and relationship sets; excludes provenance/revision.';
--rollback empty
