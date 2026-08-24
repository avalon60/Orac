--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Documents append-only authorised retrieval audit events.

--changeset clive:comment_orac_core_knowledge_retrieval_events context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_retrieval_events is 'Append-only retrieval, progressive materialisation, and evidence-backed model-submission decisions and terminal outcomes; never stores retrieved content, prompts, model output, sensitive labels, storage keys, or physical paths.';
comment on column orac_core.knowledge_retrieval_events.retrieval_id is 'Caller-generated UUID correlating one decision with one terminal outcome.';
comment on column orac_core.knowledge_retrieval_events.username_snapshot is 'Trimmed trusted-host principal name at decision time.';
comment on column orac_core.knowledge_retrieval_events.detail_json is 'Database-constructed allowlisted policy dimensions only; content, prompts, filenames, labels, sensitive metadata, storage keys, and paths are forbidden.';
--rollback comment on table orac_core.knowledge_retrieval_events is null;
