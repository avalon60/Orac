--liquibase formatted sql
--changeset clive:comment_orac_core_conversation_memory context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.conversation_memory_requests is
  'Durable idempotent work requests for bounded conversation checkpoint materialisation.';
comment on table orac_core.conversation_summary_checkpoints is
  'Immutable derived conversation summaries used only to discover authoritative source messages.';
comment on table orac_core.conversation_summary_sources is
  'Exact ordered lineage from an immutable checkpoint to authoritative source messages.';
comment on column orac_core.conversation_summary_checkpoints.source_digest is
  'SHA-256 over ordered source identities, row versions, roles, and content.';
comment on column orac_core.conversation_summary_sources.source_content_sha256 is
  'SHA-256 of the exact source message text used during materialisation.';
