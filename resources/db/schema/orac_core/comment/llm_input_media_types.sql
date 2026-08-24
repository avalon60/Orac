--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_input_media_types.

--changeset clive:comment_orac_core_llm_input_media_types context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_input_media_types is
  'Canonical exact MIME values and constrained type wildcards independent of model routing.';

comment on column orac_core.llm_input_media_types.media_type is
  'Media type.';

comment on column orac_core.llm_input_media_types.display_name is
  'Human-readable media-type name.';

comment on column orac_core.llm_input_media_types.mime_match_kind_domain_code is
  'Fixed MIME_MATCH_KIND reference domain.';

comment on column orac_core.llm_input_media_types.mime_match_kind_ref_value_code is
  'Whether the media type is exact or a constrained type wildcard.';

comment on column orac_core.llm_input_media_types.description is
  'Meaning and intended use of the canonical media type.';

comment on column orac_core.llm_input_media_types.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_input_media_types.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_input_media_types.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_input_media_types.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_input_media_types.row_version is
  'Optimistic-locking value incremented for each update.';
