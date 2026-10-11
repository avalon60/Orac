# Orac Documentation

This directory contains the canonical user, operator, and maintainer
documentation for Orac. Start with the topic matching the task you are trying
to complete.

## Get Orac Running

- [Installation](installation.md): host prerequisites, database deployment,
  credentials, and first startup.
- [SQLcl Liquibase Database Deployment](database-liquibase-deployment.md):
  on-demand core and plugin database delta deployment boundaries.
- [Configuration Reference](configuration.md): every setting shipped in
  `resources/config/orac.ini`.
- [Docker Compose Deployment](docker-compose-deployment.md): stack locations,
  services, profiles, Dockge mirroring, and control commands.
- [APEX Administration](apex-administration.md): access and troubleshoot the
  administration application.
- [Backup and Restore](backup-restore.md): protect and recover local Orac state.

## Use and Extend Orac

- [Plugins](plugins.md): plugin manifests, lifecycle, policy, configuration,
  secrets, services, database payloads, and audit boundaries.
- [Orac Knowledge Server](../plugins/orac_knowledge_server/docs/orac-knowledge-server.md):
  connect read-only MCP clients to one Core-governed project.
- [Document Ingestion](document-ingestion.md): Core-managed source storage,
  document lineage, worker configuration, APEX scope administration, chunking,
  embeddings, tags, and retrieval boundaries.
- [Knowledge Storage Maintenance](knowledge-maintenance.md): run read-only
  migration preflight, full read-only reconciliation, backfill legacy
  extractions, and migrate verified raw locators in bounded resumable batches.
- [Authorised Knowledge Retrieval](knowledge-retrieval.md): retrieve bounded
  metadata and verified normalised content through the Core-only P1-06 boundary.
- [Progressive Knowledge Materialisation Policy](knowledge-materialisation-policy.md):
  select and audit the narrowest P1-07 normalised representation that fits the
  authorised purpose and model budget.
- [Knowledge Model Evidence Submission](knowledge-model-evidence.md): wrap
  approved P1-07 Markdown/CSV/text as canonical untrusted evidence, revalidate
  the complete prompt, and invoke local text adapters under P1-08 controls.
- [Conversation Context, Memory, and RAG](conversation-context-memory-and-rag.md):
  understand what Orac persists, what enters a live prompt, which retrieval
  path handles a turn, what ships enabled or shadowed, and how to verify it.
- [Conversational Memory](conversational-memory.md): retain authoritative
  dialogue outside the live prompt and recover bounded, principal-owned source
  evidence through explicit host recall or eligible governed retrieval.
- [Governed Semantic Retrieval](governed-retrieval.md): expose one bounded,
  read-only model retrieval capability without weakening conversation,
  PROJECT, or PLUGIN authority.
- [Unified Model-Aware Context Budgeting](context-budgeting.md): allocate
  dialogue and evidence under the effective governed/runtime context limit and
  apply one provider-bound preflight guard.
- [Drop Box](../plugins/drop_box/docs/drop-box.md): install the local-file
  adapter, configure App 10020 locations, verify conversion, and troubleshoot
  ingestion.
- [Drop Box Data Lifecycle](../plugins/drop_box/docs/drop-box-data-lifecycle.md):
  scanner, conversion, retry, handoff, source identity, and Core ownership.
- [Home Assistant](../plugins/home_assistant/docs/home-assistant.md): configure
  credentials, synchronise inventory, control approved devices and scenes, and
  list devices by area.
- [Internet Retrieval](retrieval.md): configure SearXNG and Orac retrieval
  policy.
- [Runtime User Preferences](user_preferences.md): runtime preference
  precedence, validation, and TTS portability.
- [Voice Pipeline](voice-pipeline.md): wake word, recording, STT, TTS,
  playback, barge-in, and AEC.
- [Optional Atom Display](orac-atom-display.md): desktop display listener and
  event transport.

## Architecture and Protocols

- [Unified Orac Communications](communications.md): canonical requests,
  processor lifecycle, trusted principals, NDJSON/voice compatibility, and the
  reusable OpenAI Chat Completions adapter.
- [LLM-Assisted Routing Arbitration](llm-routing-arbitration.md): optional,
  bounded routing advice, provider configuration, abstention, and Core
  revalidation.
- [Conversation Context, Memory, and RAG](conversation-context-memory-and-rag.md)
- [Core Document Ingestion](document-ingestion.md)
- [Drop Box Data Lifecycle](../plugins/drop_box/docs/drop-box-data-lifecycle.md)
- [Voice Turn Lifecycle](voice-turn-lifecycle.md)
- [Home Assistant Data Lifecycle](../plugins/home_assistant/docs/home-assistant-data-lifecycle.md)
- [Plugin Execution Boundaries](agent-guardrails/avalon-55-plugin-execution-boundaries.md)
- [Plugin Audit Persistence](plugin-audit-persistence.md)
- [Plugin Audit Database/API Design](plugin-audit-db-api-design.md)
- [Protocol Contract and Release Guide](../protocol/README.md)
- [Acoustic Echo Cancellation Design](aec-design.md)

## Development Controls

Agent and maintainer guardrails remain under
[`docs/agent-guardrails/`](agent-guardrails/) because their paths are checked by
repository tooling and referenced by `AGENTS.md`.

- [Project Principles](agent-guardrails/avalon-00-project-principles.md)
- [Architecture Boundaries](agent-guardrails/avalon-10-architecture-boundaries.md)
- [Python Engineering Foundations](agent-guardrails/avalon-30-python-engineering-foundations.md)
- [Python Standards](agent-guardrails/avalon-31-python-standards.md)
- [Frontend Vite React Standards](agent-guardrails/avalon-35-frontend-vite-react-standards.md)
- [Plugin Standards](agent-guardrails/avalon-50-plugin-standards.md)
- [Plugin Execution Boundaries](agent-guardrails/avalon-55-plugin-execution-boundaries.md)
- [Security and Risk](agent-guardrails/avalon-60-security-and-risk.md)
- [Context Management](agent-guardrails/avalon-70-context-management.md)

Planning documents and work-in-progress investigations remain separate from
canonical operating guidance and should not be treated as runtime contracts.
The [Phase 2B context-budget readiness record](pending_work/phase2b-context-budget-readiness.md)
is retained as historical implementation evidence; the canonical runtime
contract is [Unified Model-Aware Context Budgeting](context-budgeting.md).
