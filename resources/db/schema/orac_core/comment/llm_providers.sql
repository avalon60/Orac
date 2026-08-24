--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_providers.

--changeset clive:comment_orac_core_llm_providers context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_providers is
  'Catalogue of reviewed Orac provider adapters, locality, metadata status, and bounded native metadata.';

comment on column orac_core.llm_providers.provider_code is
  'Provider code.';

comment on column orac_core.llm_providers.display_name is
  'Human-readable reviewed provider name.';

comment on column orac_core.llm_providers.adapter_class is
  'Reviewed Orac connector class implementing this provider.';

comment on column orac_core.llm_providers.processing_locality_domain_code is
  'Fixed PROCESSING_LOCALITY reference domain.';

comment on column orac_core.llm_providers.processing_locality_ref_value_code is
  'Reviewed processing locality classification.';

comment on column orac_core.llm_providers.metadata_status_domain_code is
  'Fixed PROVIDER_METADATA_STATUS reference domain.';

comment on column orac_core.llm_providers.metadata_status_ref_value_code is
  'Review lifecycle status for provider metadata.';

comment on column orac_core.llm_providers.effective_from is
  'Timestamp from which this provider metadata is effective.';

comment on column orac_core.llm_providers.effective_to is
  'Exclusive timestamp after which this provider metadata is no longer current.';

comment on column orac_core.llm_providers.native_properties is
  'Optional versioned provider-native metadata constrained to the P2-03 JSON allowlist.';

comment on column orac_core.llm_providers.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_providers.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_providers.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_providers.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_providers.row_version is
  'Optimistic-locking value incremented for each update.';
