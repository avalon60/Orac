# Conversational Memory

Conversational memory lets Orac remove older dialogue from the active model
prompt without deleting the authoritative conversation record. When explicit
recall wording is detected, Orac can recover bounded source-message evidence
owned by the authenticated principal.

## Enable Phase 1

1. Deploy the Core Oracle Liquibase changelog so the conversation-memory
   tables, lineage, TAPIs, and governed business package are installed.
2. Set `[conversation_memory].enabled = true` in
   `resources/config/orac.ini`.
3. Restart Orac so the Core conversation-memory worker and explicit retrieval
   policy are initialised.

The shipped default is disabled. Normal PROJECT and PLUGIN retrieval behaviour
is unchanged.

## What Is Retained

`conversations` and `messages` remain the authoritative persisted history.
Prompt history is a token-bounded projection of that history; an omitted
message is not deleted. Phase 1 does not introduce a TTL or a promise to retain
history forever. Explicit conversation deletion remains separate and future
retention/privacy policy must define automatic expiry and derived-data cleanup.

Every configured number of completed user/assistant exchanges, the scheduled
worker creates an immutable checkpoint. Closing or archiving a conversation
also makes an even trailing partial range eligible. Operational errors, system
instructions, tool results, and context injections are excluded.

Each checkpoint records the exact source range, source digest, summary profile,
embedding profile, and ordered message lineage. The derived summary is used to
find a relevant range; Orac then retrieves the original source messages before
building model evidence.

The shipped conversational-memory profile uses the local Ollama
`nomic-embed-text` model for semantic summary discovery and source selection.
The deterministic hash provider is retained only for development and isolated
tests; it is not a production semantic-retrieval profile.

## Recall Behaviour

Phase 1 uses conservative explicit wording such as:

- “What did we decide about image support?”
- “Do you remember what we discussed earlier?”
- “What did we agree last time?”

The wording policy only decides whether to ask for recall. It does not perform
retrieval or supply authority. The lower-level conversation-memory service can
also be invoked directly by trusted host code and always derives ownership from
the authenticated runtime context.

Memory evidence is treated as quoted, untrusted historical data. Whole source
messages are admitted only while both the configured evidence ceiling and the
selected model's registered context limit have room for them. If model context
capacity is unknown or the final prompt is unsafe, memory is omitted and normal
dialogue continues.

## Security and Provenance

- Database retrieval joins every checkpoint to the active authenticated user.
- Requests cannot select a username, principal, conversation, checkpoint,
  project, plugin, or database scope.
- Cross-principal requests return the same no-evidence shape as absent memory.
- Runtime access is limited to `orac_code.conversation_memory_api`; no model or
  plugin receives table privileges.
- Assistant provenance records the retrieval ID, initiator, checkpoint and
  conversation identities, source message identities, range, and truncation
  state.
- Summaries never override contradictory or missing source messages.

Retrieval is read-only. LLM-controlled deletion, mutation, fact promotion, and
scope changes are not supported.

## Failure and Operations

Materialisation requests use `PENDING`, `RETRY_WAIT`, `COMPLETED`, and `FAILED`
states. Source embeddings are created idempotently for the pinned Phase 1
profile. Checkpoint, exact lineage, and request completion are one transaction.
Source row-version or content-digest changes invalidate the attempt.

Summarisation or embedding failure never blocks dialogue or live-history
projection. Retryable work uses bounded backoff; terminal failures retain a
bounded error code/message for diagnosis.

Monitor:

- retained `messages` and `message_embeddings` growth;
- request counts by status and retry age;
- checkpoint/source lineage counts;
- worker health and terminal failures;
- grounded, no-evidence, unavailable, and prompt-safety omission outcomes.

## Governed Model Retrieval

Phase 2A adds one read-only `retrieve` capability above the same independent
conversation-memory service. A model may supply only a query and an advertised
logical domain. Principal, conversation ownership, PROJECT scope, plugin
identity, entitlements, and database scope remain host-derived. See
[Governed Semantic Retrieval](governed-retrieval.md).

Phase 2B remains deferred and may later introduce a unified model-aware
allocator across instructions, dialogue, web, knowledge, memory, and response
allowance. MCP remains deferred; any future MCP server must be a thin facade
over Orac-owned services.
