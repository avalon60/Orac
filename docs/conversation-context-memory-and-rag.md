# Conversation Context, Memory, and RAG

Orac keeps the authoritative conversation record separate from the temporary
prompt sent to a model. It can also retrieve bounded evidence from previous
conversations and authorised PROJECT or PLUGIN knowledge without giving a
model control over identity, scope, permissions, or storage.

NDJSON, voice, internal, and OpenAI-compatible callers reach these same
controls through `OracRequestProcessor`. Adapter-supplied history is
request-local context; it does not replace the persisted record or host system
policy, and adapter scope bounds never grant retrieval authority.

Use this guide to understand which mechanism handles a turn, what is enabled
in the shipped configuration, how to request grounded answers, and how to
verify the result. The linked feature guides remain the detailed technical
contracts.

## The Four Layers

| Layer | Purpose | What it is not |
| --- | --- | --- |
| Persisted conversation history | Stores the durable user and assistant event record in Oracle. | It is not copied wholesale into every model prompt. |
| Live prompt projection | Selects recent useful dialogue, active instructions, current context, and the current request. | Omission from the prompt does not delete a message. |
| Memory and knowledge retrieval | Selects authorised CONVERSATION, PROJECT, or PLUGIN evidence when a route or eligible model requests it. | Retrieved evidence is untrusted data, not a system instruction or permission grant. |
| Context budgeting | Accounts for instructions, dialogue, evidence, tools, response allowance, and safety headroom. | It does not perform retrieval or change retention. |

Persisted history is therefore not RAG by itself. In Orac, RAG means that
selected, provenance-backed evidence is retrieved and added to the temporary
model context.

## What Ships Now

The shipped file is `resources/config/orac.ini`. An environment override takes precedence at runtime,
and database capability records can still change the
effective runtime, so a configured switch is not proof that every model or
principal can use the feature.

| Capability | Shipped setting | Effective shipped behaviour |
| --- | --- | --- |
| Recent conversation history | `[context].enable_context_history = true` | Recent dialogue is selected non-destructively for the ordinary prompt. |
| Unified context planning | `[context_budget].enabled = true` | The planner runs for primary dialogue. |
| Context enforcement | `[context_budget].shadow_mode = false` | The unified plan is enforced for primary dialogue and remains independent of governed-domain discovery and tool injection. |
| Conversational memory | `[conversation_memory].enabled = true` | Checkpoint materialisation and explicit host-policy recall are active when their dependencies are healthy. |
| Governed model retrieval | `[governed_retrieval].enabled = true` | The retrieval tool is available only to exact models with verified capability evidence and safe runtime health. |
| Phase 2A PROJECT binding | `[governed_retrieval].project_scope = PROJECT:ORAC_CORE` | The host may offer this exact authorised project; the model cannot replace its scope key. |
| Phase 2C discovery | `[governed_retrieval].domain_discovery_enabled = true` | Ranked authorised domain offers are model-facing for eligible models. |
| Phase 2C shadow observation | `[governed_retrieval].domain_discovery_shadow_mode = false` | Shadow is available only as an explicitly selected diagnostic state. |
| Governed-tool context floor | `[governed_retrieval].min_effective_context_tokens = 32768` | Smaller models skip automatic Phase 2C/tool retrieval while explicit bounded knowledge retrieval remains available. |
| Knowledge ingestion | `[knowledge].enabled = true` | The Core worker can ingest, chunk, and embed accepted documents. |
| Dialogue knowledge retrieval | `[knowledge.dialogue].enabled = true` | Authorised scoped retrieval and ordinary host-controlled PROJECT grounding are active. |
| Automatic project search | `[knowledge.dialogue].automatic_project_search_enabled = true` | Ordinary authenticated questions search content across all currently authorised active PROJECT scopes without model tools. |
| Automatic project search deadline | `[knowledge.dialogue].automatic_project_search_timeout_seconds = 10` | The host and Oracle driver bound each automatic search to ten seconds. |
| Whole-content retrieval | `[knowledge.retrieval].enabled = true` | P1-06 authorised normalised-content materialisation is available within its hard limits. |
| Progressive materialisation | `[knowledge.materialisation].enabled = true` | P1-07 can select the narrowest approved representation for an explicit document task. |
| Model evidence submission | `[knowledge.model_evidence].enabled = true` | P1-08 can submit approved normalised text for an eligible exact local model. |
| Model evidence context floor | `[knowledge.model_evidence].min_effective_context_tokens = 32768` | Below this per-model floor, the turn skips P1-07/P1-08 and retains bounded RAG. |

The final governed-retrieval mode is resolved per exact model:

- `NONE` when verified structured tool calling is absent;
- `BUFFERED` when structured calls are verified but safe streamed framing is
  not;
- `STREAMING` when structured and streamed evidence, provider framing, and
  operational health are all acceptable.

The feature switch never creates model capability evidence or grants a user
access to a knowledge scope.

## How a Turn Is Handled

Orac uses the following high-level flow:

1. Persist the real user message in the authoritative conversation.
2. Apply core route precedence: explicit internet selection, explicit
   knowledge syntax, deterministic plugin interception, internet policy, then
   automatic authorised PROJECT search before ordinary dialogue.
3. Retrieve any selected web or authorised local-knowledge evidence.
4. For an explicit single-document summary, review, extraction, analysis, or
   comparison, use P1-06/P1-07/P1-08 only when the selected model passes the
   effective-context gate; otherwise retain the bounded chunk grounding path.
5. If explicit recall wording matches, retrieve principal-owned source-message
   evidence from compatible conversational-memory checkpoints.
6. Assemble the live prompt and run the unified context plan. In the shipped
   enforced mode, Orac applies the plan to the provider-bound prompt.
   Independent retrieval ceilings and final prompt-safety checks still apply.
7. For an otherwise ordinary eligible turn with no web, local-knowledge, or
   explicit-memory evidence pack already selected, discover and advertise the
   remaining conversation and plugin governed-retrieval domains. PROJECT
   descriptor discovery is skipped because the host has already searched
   authorised project content.
8. Required turns use a compact tool-decision request. After a valid call, the
   existing full-context prompt is used for the grounded, tools-disabled answer;
   decision prose can never override the host requirement.
9. Persist only the authoritative final assistant answer and safe provenance.
   Ephemeral tool-call and tool-result messages are not conversation turns.

An explicit or implicit local-knowledge route is deterministic and terminal.
If it is denied, unavailable, or has no qualifying evidence, Orac does not let
an ordinary model answer bypass that outcome. Governed model retrieval is a
separate path for eligible ordinary turns; it does not replace deterministic
route selection.

## How to Use It

### Continue the Current Conversation

Ask a normal follow-up. Recent selected exchanges remain available through the
live prompt projection while they fit the active history policy. Older omitted
messages remain persisted.

When an ordinary follow-up refers to an earlier subject with wording such as
`it`, `this`, or `that`, automatic PROJECT retrieval includes the nearest
preceding self-contained user question in its search query. Intermediate
referential questions, assistant answers, and prior
evidence are excluded from that query, and the host performs a fresh
authorisation check for the new turn.
The host creates one embedding from this contextual query while lexical
matching remains focused on the current question. A bounded deterministic
expansion helps terse questions about tooling, command-line use, and model
interfaces retrieve passages that state concrete setup capabilities.
When local evidence grounds the answer, the model prompt retains preceding
user questions but excludes prior assistant answers. This prevents an earlier
unsupported model claim from becoming apparent evidence on later grounded
turns.

Entity-bearing questions use bounded literal constraints in addition to the
normal 65/35 hybrid ranking. Suitable entity or identifier anchors can reserve
up to half of the evidence slots, while the remaining slots retain conceptual
ranking and neighbour behaviour. Anchor excerpts are match-centred and coverage
is recalculated after all character limits. Retrieval remains non-exhaustive:
absence from the selected excerpts does not establish absence from the source
document or wider corpus, and a name appearing near text does not by itself
establish authorship or attribution. For bounded local-knowledge answers, Orac
buffers streamed output by sentence and rewrites unsupported source-absence
claims before they reach clients, persistence, or speech output. Other response
routes retain their existing immediate streaming behaviour.

### Recall an Earlier Conversation

Use explicit recall wording when you want the host policy to request memory:

```text
What did we decide about image support?
Do you remember what we discussed earlier?
What did we agree last time about the database build?
```

Orac searches derived summaries to locate a range, then admits bounded original
source messages rather than trusting the summary as the answer. An eligible
governed model may also request the CONVERSATION domain on an otherwise
ordinary turn, but explicit wording is the predictable operator-facing route.

### Ask an Authorised Knowledge Source

Use a configured alias or canonical scope when the source must be explicit:

```text
Consult PROJECT:ORAC_CORE knowledge source for the installation procedure.
Query the PLUGIN:drop_box knowledge base for classification tag guidance.
What does the Orac documentation say about plugin installation?
```

The first two examples select an exact source. The third and ordinary questions
use automatic content search across all authorised projects. The authenticated
principal still needs a current Oracle `USE` privilege, and each contributing
scope must be active.

Use explicit scope syntax when one exact source is mandatory. Scope-neutral
requests such as `Check your knowledge base for ...` search all authorised
PROJECT scopes and require documentary evidence. Automatic PROJECT retrieval
does not depend on model eligibility or tool-calling support. PLUGIN retrieval
retains its existing plugin-private boundary.

## Prerequisites

| Mechanism | Required state |
| --- | --- |
| Recent history | Context history enabled and an active persisted conversation. |
| Conversational recall | Registered principal, retained source messages, completed compatible checkpoints, embedding service availability, and safe model headroom. |
| PROJECT knowledge | Active project and knowledge scope, searchable completed chunks, and a current principal-to-scope `USE` privilege. |
| PLUGIN knowledge | Eligible installed plugin scope, searchable content, current `USE` privilege, and any required trusted runtime bridge. |
| Materialised model evidence | Exact local text model, positive governed context ceiling, effective context of at least 32,768 tokens, one authorised document version, and enabled dialogue/P1-06/P1-07/P1-08 switches. |
| Governed model retrieval | Enabled coordinator, available mediator, positive registered context limit, exact verified tool capability evidence, provider support, and acceptable health. |
| Phase 2C discovery | Valid discovery embedding profile and authorised catalogue; shipped mode advertises qualifying authorised domains. |

Scope names, principals, conversation IDs, checkpoint IDs, plugin identities,
and database selectors are host-derived. A model query cannot nominate or
change them.

## Verify the Runtime

Start with the configured service state:

```bash
bin/orac.sh status
.venv/bin/python scripts/probe_governed_retrieval.py --pretty
```

The bounded probe validates provider framing for a fixed fixture. Its result is
review evidence only; it does not insert or update model capability evidence.

Useful startup log markers include:

```text
Conversational memory initialised in explicit-policy mode.
Governed model retrieval coordinator initialised.
Unified context budgeting initialised: ...
Knowledge dialogue retrieval initialised with scope status ...
Knowledge model evidence initialised (shadow_mode=false, min_effective_context_tokens=32768).
```

At startup and request time, an unknown runtime limit records
`CTX_RUNTIME_LIMIT_UNKNOWN` and uses the governed registry ceiling. A model
below the floor records `MAT_SUB_MODEL_CONTEXT_BELOW_MINIMUM`; these warnings
contain safe identifiers and accounting values, not prompt or evidence text.

When diagnostic shadow discovery is explicitly selected, eligible turns may
record bounded `Governed domain discovery` telemetry without exposing the
Phase 2C handle-enumerated schema to the model. In the shipped active state,
advertised qualifying domains are model-facing.

Successful assistant provenance can identify the route, retrieval outcome,
safe reason codes, controlled scope or conversation identities, selected
source identities, truncation state, governed mode, and audit correlation. It
does not retain evidence text, prompts, reasoning, raw tool frames, or model
arguments in the governed-retrieval audit.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| A recent fact is missing | Confirm context history is enabled and inspect whether the exchange was outside the current prompt projection. |
| Explicit recall returns no evidence | Confirm the principal owns retained messages, compatible checkpoints completed, embeddings are available, and recent prompt messages were correctly excluded from duplicate recall. |
| A knowledge request is denied | Confirm the authenticated username, active scope, and current Oracle `USE` privilege. Do not repair this with direct table DML. |
| A knowledge request has no evidence | Confirm ingestion completed, the active immutable knowledge profile has current native vectors, and either the semantic or lexical branch admitted relevant chunks. |
| An explicit whole-document task uses bounded RAG | Confirm the exact local text model's lower registry/runtime context ceiling is at least 32,768 tokens and inspect the safe model-evidence readiness reason. |
| The model never receives a retrieval tool | Confirm the exact model has verified structured-tool evidence, a positive context limit, provider support, and an available authorised domain. |
| Governed retrieval falls back to buffered mode | Inspect streamed framing health and capability evidence; operational suppression does not rewrite the governed model record. |
| Context decisions appear in metadata but prompts are unchanged | Confirm whether an environment override has selected `[context_budget].shadow_mode = true`; the shipped setting is enforced mode. |
| Discovery telemetry appears but advertised domains do not change | This is expected while discovery is shadowed and `domain_discovery_enabled` remains false. |

## Security and Retention Boundaries

- Persisted history and temporary prompt context are different data sets.
- Prompt omission never deletes the authoritative message row.
- No automatic conversation TTL or derived-data cleanup policy is currently
  promised.
- Retrieved evidence is quoted, bounded, untrusted data.
- Models cannot mutate memory, promote statements into facts, change scope,
  or select another principal.
- Tool calls and tool results exist only in the active provider loop unless
  safe bounded provenance is deliberately recorded.
- MCP is not part of the current retrieval surface.

## Rollout Criteria

### Adjust Progressive Model Evidence

P1-06, P1-07, and P1-08 ship enabled, with a 32,768-token per-model effective
context floor. The effective ceiling is the lower of the governed registry
value and an observed provider runtime value. Keep the shipped floor unless
representative evidence turns establish a different safe operating point.
Disable `[knowledge.model_evidence]`, `[knowledge.materialisation]`, or
`[knowledge.retrieval]` independently when a narrower rollback is required;
ordinary authorised RAG remains available.

### Operate Unified Context Budgeting

The shipped profile has `enabled = true` and `shadow_mode = false`. Continue to
review estimate-to-actual deltas for representative ordinary, knowledge-backed,
memory-backed, governed-tool, streaming, and output-retry turns across every
supported provider/runtime/model combination. A diagnostic rollback to
`shadow_mode = true`, or restoration to enforced mode, is an explicit
configuration change followed by an Orac restart; telemetry never changes the
setting automatically.

### Diagnose Phase 2C Domain Discovery

The shipped discovery state is active:

```ini
domain_discovery_enabled = true
domain_discovery_shadow_mode = false
```

For diagnostic/development observation without model-facing offers, select:

```ini
domain_discovery_enabled = false
domain_discovery_shadow_mode = true
```

Restart Orac after a configuration change. The ambiguous true/true pair is
rejected.

## Detailed Contracts

- [Conversational Memory](conversational-memory.md)
- [Dialogue Routing](dialogue-routing.md)
- [Governed Semantic Retrieval](governed-retrieval.md)
- [Unified Model-Aware Context Budgeting](context-budgeting.md)
- [Document Ingestion](document-ingestion.md)
- [Progressive Knowledge Materialisation Policy](knowledge-materialisation-policy.md)
- [Knowledge Model Evidence Submission](knowledge-model-evidence.md)
- [RAG Usage Privileges](rag-usage-privileges.md)
- [Configuration Reference](configuration.md)
