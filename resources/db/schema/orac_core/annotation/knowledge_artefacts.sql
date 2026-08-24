--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Adds governed metadata for normalised knowledge artefacts.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:annotate_orac_core_knowledge_artefacts context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_artefacts annotations (
  add if not exists display_name 'Knowledge artefact',
  add if not exists plural_display_name 'Knowledge artefacts'
);

--changeset clive:annotate_orac_core_kn_artf_artefact_id context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_artefacts modify artefact_id annotations (
  add if not exists display_name 'Artefact identifier',
  add if not exists semantic_role 'primary_key',
  add if not exists data_kind 'identifier'
);

--changeset clive:annotate_orac_core_kn_artf_extraction_id context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_artefacts modify extraction_id annotations (
  add if not exists display_name 'Extraction',
  add if not exists semantic_role 'foreign_key',
  add if not exists data_kind 'identifier',
  add if not exists rel_target 'orac_core.knowledge_extractions.extraction_id',
  add if not exists rel_type 'belongs_to',
  add if not exists rel_cardinality 'many_to_one',
  add if not exists rel_optionality 'required',
  add if not exists rel_basis 'constraint:kn_artf_kn_ext_fk1'
);

--changeset clive:annotate_orac_core_kn_artf_storage_key context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_artefacts modify storage_key annotations (
  add if not exists display_name 'Managed storage key',
  add if not exists semantic_role 'logical_reference',
  add if not exists data_kind 'identifier'
);
