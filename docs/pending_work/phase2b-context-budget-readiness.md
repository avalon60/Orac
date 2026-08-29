# Phase 2B Context-Budget Readiness Record

This historical record captured the evidence needed before planning Phase 2B
unified model-aware context budgeting. Phase 2B has since been implemented;
the canonical runtime and rollout contract is now
[Unified Model-Aware Context Budgeting](../context-budgeting.md).

## Readiness outcome

Phase 2B planning is unblocked. Phase 1 retention/conversational memory and
Phase 2A governed retrieval now provide grounded runtime evidence, and the
existing context-limit, response-reserve, estimator, and final-guard contracts
have been identified. Phase 2B remains independent from Phase 2A.

The current working tree is intentionally uncommitted and contains earlier
knowledge-retrieval work. Preserve that baseline and do not use a broad reset,
checkout, or indiscriminate commit when beginning Phase 2B.

## Grounded acceptance evidence

Development acceptance on 29-Aug-2026 used two retained conversations owned by
the authenticated principal:

- Conversation A (`conversation_id=25`) contains 20 completed exchanges. Turn
  1 records: “Image processing is not currently a priority for Orac; support
  for the main document formats is the focus.”
- Conversation B (`conversation_id=26`) supplies the later trusted retrieval
  context without directly including Conversation A.
- The ordinary `normal` live-history projection retained 15 of 40 messages and
  began at turn 26. The source decision (`message_id=99`) was absent from that
  projection while all 40 authoritative message rows remained stored.
- Immutable checkpoint 3 covers Conversation A turns 1–40 using materialisation
  profile `conversation-memory-v2`, `nomic-embed-text:latest`, 768 dimensions,
  and exact checkpoint-to-message lineage.
- Direct trusted-host retrieval returned `grounded`, selected checkpoint 3 and
  source messages including 99 and 100, used 268 of a 300-token evidence
  allowance, marked the result truncated, and returned exact provenance.
- The same request for a nonexistent principal returned the normal
  `no_evidence` shape with no provenance or evidence.
- A real streamed Ollama tool turn selected `STREAMING`, emitted an early
  `CONVERSATION` call before visible assistant content, executed retrieval once,
  streamed only the tools-disabled final answer, and accurately reproduced the
  document-format-over-image decision.

The earlier hash-derived checkpoints remain immutable. The deployed
`MESG_EMB_UK1` key now includes `embedding_model`, allowing the authoritative
source messages to retain both historical and current derived embedding
profiles. The previously retrying versioned requests completed successfully;
no Core/API/CODE objects remained invalid.

## Phase 2A telemetry baseline

The tested registry/runtime/model tuple was:

- registry `llm_id=2`, row version 13;
- provider `ollama`;
- model `qwen3.6-48K:latest`;
- registered context limit 49,152 tokens;
- exact model revision
  `16c2c5e174ffa5a4cb1afc3425fb02f33296dc72ab36bd236608629147c1ded0`;
- both structured and streamed structured tool capabilities in
  `BOUNDED_PROBE_VERIFIED` state.

Observed streamed governed-retrieval turn:

- tool timing `EARLY`;
- zero visible characters before the tool call;
- no continuation recovery and no reason codes;
- prompt 633 tokens, completion 59 tokens, total 692 tokens;
- final retrieval provenance retained checkpoint, conversation, message, range,
  initiator, and truncation metadata without persisting tool-loop messages.

Observed direct streamed answer with the tool advertised but unused:

- one invocation, no retrieval, no second continuation;
- 128 characters before commit and a measured 316 ms commit-gate delay;
- first user-visible yield at 1,039 ms and total completion at 1,541 ms for the
  sampled local run;
- prompt 418 tokens, completion 53 tokens, total 471 tokens.

These timings are a single local baseline, not model-name eligibility rules.
Operational health may suppress streaming without changing governed capability
evidence.

## Existing context and model contracts

### Authoritative model capability source

`orac_api.llm_registry_v` supplies the effective `llm_id`, provider, model,
context policy, positive `max_context_tokens`, enabled state, properties, and
row version. Phase 2B should reuse this registry snapshot and fail safe when the
limit is missing, stale, disabled, or unavailable. Provider-reported inventory
is compatibility evidence, not a replacement authority for the registered
limit.

### Existing estimators and reserves

- Ordinary recent-dialogue selection uses the legacy approximate
  `len(text) // 4` estimator plus four tokens per role header.
- `ConservativeUtf8TokenEstimator` provides the stronger reusable contract:
  representation-aware UTF-8 estimates, per-part overhead, a 20 percent safety
  margin, and exact rendered-prompt/envelope estimation.
- The normal generation response allowance is derived from `num_predict`, with
  a configured default of 2,048 tokens.
- Strict knowledge evidence submission fixes the output reserve at 2,048,
  re-reads the model registry, estimates the fully rendered prompt, reserves at
  least five percent/256 safety tokens, and caps evidence at 25 percent of
  usable input.

### Current fragmented allocation paths

- Recent dialogue has an independent economy/configured budget (normal default
  1,200) and a 300-token reserve. Selection walks newest to oldest and includes
  the message that reaches or exceeds the budget.
- Explicit conversational memory and Phase 2A governed retrieval each derive a
  bounded allowance from the selected model's registered context limit and run
  a local final check after evidence/tool-result serialization.
- PROJECT knowledge and PLUGIN self-scope retrieval keep their existing domain
  limits and authorisation contracts. The Phase 2A model-facing serializer adds
  the common final evidence-character bound for `CONVERSATION`, `PROJECT`, and
  `PLUGIN`, followed by the governed final context check.
- Progressive knowledge materialisation has its own stronger immutable
  submission guard.
- System instructions, current dialogue, ordinary recent history, web evidence,
  normal RAG evidence, and the response allowance do not yet share one universal
  allocator or one universal final model-context guard.

## Inputs for the Phase 2B plan

The Phase 2B plan should modernise context accounting without changing the
independent retrieval trust models. It should:

1. define one registry-derived usable context envelope for the exact effective
   model and response allowance;
2. preserve mandatory instructions and the current user request;
3. allocate bounded shares/priorities for recent dialogue, web evidence, local
   RAG, and conversational memory;
4. reuse the conservative estimator and estimate the exact final provider
   representation, including tool framing where applicable;
5. retain recent dialogue directly while allowing older authorised evidence to
   compete only inside the remaining budget;
6. finish with one universal pre-invocation safety guard, without weakening the
   stricter knowledge-evidence guard or any domain authorisation contract;
7. record content-free allocation and omission reason codes suitable for
   operations and regression tests.

Phase 2B must not alter checkpoint topology, make trimming depend on successful
materialisation, merge PROJECT/PLUGIN/conversation storage, or make model
identity the security boundary.
