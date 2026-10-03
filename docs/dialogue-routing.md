# Dialogue Routing

Normal Orac dialogue uses one core-owned routing sequence. Route selection does
not bypass plugin policy, retrieval policy, persistence, or prompt boundaries.

All transports enter this sequence through the canonical communications
processor. NDJSON and OpenAI-compatible adapters translate wire shapes only;
they cannot grant plugin capabilities, knowledge scopes, confirmation, or
identity. Candidate enablement, declaration, and side-effect-free policy
eligibility are checked before deterministic arbitration. When explicitly
enabled, the bounded [LLM routing adviser](llm-routing-arbitration.md) may judge
only an unresolved set of already-permitted plugin candidates. Final policy and
any single-use confirmation are evaluated only for the revalidated selected
candidate.

## Precedence

1. Explicit user route-selection controls, currently direct internet commands
   such as `Search the web for ...`.
2. Explicit knowledge-source syntax, including unknown names, which terminates
   as authorised retrieval, safe denial/unavailability, or clarification.
3. Scope-neutral explicit local-retrieval intent, which reserves the governed
   retrieval path without selecting or granting a scope.
4. Deterministic plugin interception from validated plugin metadata.
5. Existing internet-retrieval policy and SearXNG routing.
6. Semantic plugin hints retained for compatibility, with optional LLM advice
   when deterministic matching remains unresolved or ambiguous.
7. Automatic content search across every authorised active PROJECT scope.
8. Ordinary LLM response.

The deterministic route gates and precedence remain separate from
model-governed retrieval. The optional adviser cannot select a late retrieval
or web-search route; those authorised routes have already run at their existing
positions in the sequence.
A selected local-knowledge route, including a terminal denial, unavailability,
or no-evidence result, is resolved before an ordinary model can receive the
governed retrieval tool. See
[Conversation Context, Memory, and RAG](conversation-context-memory-and-rag.md)
for the complete turn flow.

An explicit internet command is evaluated by the existing `[retrieval]` policy
before a network request is made. A weather plugin therefore cannot capture
`Search the web for tomorrow's weather in Leeds`, but `What's the weather
forecast?` can still be intercepted by the weather plugin.

With the shipped `internet_search_mode = explicit_only`, current-looking
questions do not automatically search the internet unless an existing
high-risk rule treats the request as explicit. Use a direct route-selection
command to guarantee an internet request. Automatic current-information
routing requires a deliberate policy change to `auto_safe`; it is not promised
by the first local-knowledge release.

## Local Knowledge Turn Triggers

Explicit local knowledge routing is deterministic. Ordinary authenticated
questions also receive a host-controlled content search across all active
PROJECT scopes for which the user currently has `USE` permission. This search
runs before answer generation and does not depend on model tool support,
project names, descriptions, aliases, or Drop Box location metadata.

### Explicit Named Source

The explicit grammar is:

```text
<verb> [the] <source-name> knowledge <kind>

<verb> = use | search | query | consult
<kind> = base | source
```

`[the]` means that the article is optional. `<source-name>` must be either a
configured alias or a canonical `PROJECT:<project_code>` or
`PLUGIN:<plugin_id>` identity. For example, both of these match:

```text
Use drop box knowledge base to answer: How are plugins installed?
Use the drop box knowledge base to answer: How are plugins installed?
```

Canonical identities can be selected directly:

```text
Consult PROJECT:ORAC_CORE knowledge source for the installation procedure.
Query the PLUGIN:drop_box knowledge base for classification tag guidance.
```

An explicit source name that is unknown, inactive, or unauthorised terminates
through clarification, safe unavailability, or safe denial. It does not fall
through to a plugin or an ordinary LLM answer.

The unnamed form is also recognised:

```text
<verb> [the] knowledge <kind>
```

For example, `Search the knowledge base for plugin installation` searches all
authorised active PROJECT scopes without asking for a project.

Drop Box location codes and display names remain source provenance. They do not
control whether ordinary project content is searched. A location alias can
still be configured when a user must explicitly select one exact scope.

### Scope-Neutral Local Retrieval Intent

Requests that explicitly ask Orac to consult local knowledge also produce a
scope-neutral required-retrieval signal when they are not already resolved by
the earlier source-selection route. The bounded family recognises actions such
as `check`, `search`, `query`, `consult`, `use`, `retrieve ... from`, and
`look ... up in` when paired with a local source phrase such as `knowledge
base`, `knowledge source`, `local knowledge`, `internal knowledge`, `project
knowledge`, `documentation`, or `docs`. Determiners and possessives such as
`the`, `your`, `our`, and `my` are accepted.

For example:

```text
Check your knowledge base for the fictional Project Lantern release procedure.
Look the fictional Atlas Finch decision up in the documentation.
According to your knowledge source, how does the fictional Zephyr lattice work?
```

These examples are deliberately fictional because this operator guide may be
ingested as `ORAC_DOCS`; production regression wording belongs in executable
tests, not in a searchable evidence source.

This signal cannot create authority or override an explicit internet route. It
uses the host-controlled authorised-project search and therefore works with a
model that has no tool-calling support.

### Ordinary Questions

For a registered user, ordinary questions search document content across all
currently authorised active PROJECT scopes before the model answers. An
implicit project alias does not narrow that search. Relevant evidence is added
with document and project provenance; an above-threshold result therefore
grounds the answer even when the question names no project.

A successful search with no relevant evidence allows an ordinary general
answer without claiming documentary support. An explicit local-document
request instead reports that no matching evidence was found. If automatic
retrieval fails, an ordinary answer is prefixed with a host-authored notice;
an explicit document request terminates as unavailable. Plugin-private scopes
remain behind their existing plugin route and are not included.

For a referential follow-up such as `What tools does it rely on?`, the host
adds the nearest preceding self-contained user subject to the retrieval query. It
does not reuse assistant prose or previously retrieved evidence. Authority is
revalidated when the new search runs and again before materialisation.
The single semantic embedding uses that contextual query. Lexical matching
keeps the current question's intent and applies a small deterministic expansion
for tooling, command-line, and model-interface questions. The same recognised
intents add neutral focus terms to the single semantic query so concrete
setup passages can outrank broad definitions.
For a grounded local-document turn, recent user questions remain in model
context, while prior assistant answers are omitted so unsupported model prose
cannot override the newly retrieved evidence.

### Broad Document Intents

When retrieved chunks resolve to one document, the explicit verbs
`summarise`, `summarize`, `review`, `extract`, `analyse`, `analyze`, and
`compare` mark a trusted P1-08 materialisation purpose. They do not themselves
authorise content. Existing RAG must resolve exactly one document version, and
P1-06 and P1-07 still perform current authorisation, verification, selection,
and downgrade decisions. Ordinary questions retain the existing chunk-grounded
route.

P1-06, P1-07, and P1-08 ship enabled, but the broad path runs only when the
selected local text model's effective registry/runtime context is at least
32,768 tokens. A model below that floor retains the bounded chunk-grounded
route and records a safe readiness reason.

When P1-08 follow-ups are enabled, another explicit broad request in the same
authorised scope may reuse only the registered same-document target state. It
repeats P1-06 and P1-07 and is subject to cumulative round, byte, token, member,
chunk, row, and elapsed-time ceilings. Model prose is never interpreted as a
retrieval request.

### Triggering Versus Grounding

Matching explicit syntax selects a required local-knowledge route; it does not
guarantee evidence. Oracle derives eligible projects from current permissions,
validates active scope state, and applies semantic and lexical thresholds. A
required route with no qualifying chunks terminates as `no_evidence`. An
ordinary automatic search with no qualifying chunks may continue to general
model knowledge.

## Knowledge Scope

Dialogue retrieval is enabled in the shipped `[knowledge.dialogue]`
configuration. An explicit `enabled = false`, or a configuration that omits
the setting, keeps retrieval disabled.
Database-maintained RAG usage privileges bind the exact authenticated username
to canonical relational scope identities displayed as:

```text
PROJECT:<project_code>
PLUGIN:<plugin_id>
```

Orac-wide documentation uses `PROJECT:ORAC_CORE`. Drop Box-specific
documentation uses `PLUGIN:drop_box`. Project scopes must be active in
`orac_code.project_registry_v`. Plugin scopes must pass the same enabled,
install, configuration, dependency, database, and readiness gates used by the
runtime plugin registry.

Core owns that pure eligibility policy in
`orac_core.plugin_registry_policy`. `model.plugin_registry` remains the
database/runtime adapter and reuses the Core predicate; knowledge discovery
uses the same predicate rather than importing the model adapter.

`ORAC_CORE` and its canonical project scope are seeded by the Core database
install. They are explicit platform metadata and are not inferred from Drop
Box configuration. If an administrator has deactivated the project, reactivate
it through the published maintenance boundary before enabling dialogue
retrieval:

```sql
begin
  orac_code.project_registry_api.upsert_project(
    p_project_code => 'ORAC_CORE',
    p_display_name => 'Orac Core',
    p_description  => 'Orac-wide architecture, operations, and product documentation.',
    p_active_yn    => 'Y'
  );
end;
/
```

Run this as an administrative identity already entitled to execute that API;
do not insert directly into `orac_core.project_registry`.

The Drop Box plugin seeds the `ORAC_DOCS` adapter location separately. That
location targets `PROJECT:ORAC_CORE`; its location code is not another scope or
an automatic dialogue alias.

Privileges reference `orac_core.users.user_id` and the canonical scope id;
`TYPE:key` is derived from immutable project/plugin identifiers. Usernames are
trimmed at authentication boundaries but preserve case.

Aliases are configuration conveniences only. Unknown or inactive principals
and missing, expired, or revoked privileges map to `knowledge_denied`.
Inactive/ineligible scopes and authorization service failures map to
`knowledge_unavailable`. Unknown or missing scopes remain clarification routes.
These routes are terminal: no corpus query, grounding prompt, response LLM,
web retrieval, plugin fallback, or ordinary generation occurs.

Configured scope data is checked at startup. The automatic database API does
not cache authority or evidence across turns: it derives permissions and active
projects for every search, and materialisation revalidates authority again.
Startup registry errors disable retrieval execution but keep routing active, so
explicit knowledge requests terminate as unavailable without plugin or LLM
execution and without exposing whether a requested corpus exists.

## Retrieval

The runtime reads current, completed chunks only through the definer-rights
`orac_code.knowledge_retrieval_api`. Its automatic entry point derives every
eligible active PROJECT scope inside Oracle from the authenticated user's
current `USE` permissions before opening the bounded cursor. The runtime has no
direct searchable-view grant or synonym and never loads stored vectors into
Python. The package accepts one transient, validated query vector for the
active immutable profile and runs two globally bounded branches:

- Oracle cosine-distance ranking over native `VECTOR(768,FLOAT32)`, admitted by
  the active profile's semantic threshold and `FETCH EXACT` candidate limit;
- lexical coverage for ordinary terms, exact identifiers containing `.`, `_`,
  or `-`, phrases, and source names, admitted independently at `0.25`.

The lexical threshold is not a universal hard gate. A strong paraphrase may
enter through the semantic branch with no lexical match, while exact names,
filenames, configuration properties, database objects, and versions remain
strong lexical candidates. Oracle returns only the global union of at most 50
rows from each branch, with project, document, version, chunk, and source
provenance plus raw semantic/lexical scores and deterministic ranks.
The host applies weighted reciprocal-rank fusion (`0.65` semantic, `0.35`
lexical, rank constant `60`) and then enforces selected-chunk, per-chunk,
total-context, and deduplication limits. Ordinary navigation demotion and RRF
ordering remain unchanged. A separate deterministic constraint-coverage stage
may reserve at most half of the selected slots for suitable quoted literals,
names, filenames, identifiers, acronyms, and versions from the current query.
An occurrence is not sufficient by itself: an anchor must also clear the
semantic threshold or occur in the leading evidence document with independent
topical overlap. Anchor excerpts are centred on the actual match so coverage is
measured against the text sent to the model, not the untruncated chunk.

When a high-confidence literal has no suitable candidate in the initial union,
the host may make one bounded literal-recovery call through the same authorised
database boundary. It reuses the query vector and all scope, principal, plugin,
searchability, and active-profile checks, returns at most
`min(16, max_selected_chunks * 2)` candidates, and has its own retrieval ID and
terminal audit outcome. No second embedding or model call is made. The runtime
uses additive `*_v2` package entry points because positional Oracle cursor
outputs must remain last; the original three entry points remain compatible.

The initial `0.60` semantic threshold is calibrated specifically for the
pinned `knowledge-v1` Nomic digest, `search_document:`/`search_query:` input
transforms, and `truncate=false`. It is not a generic threshold for other
models, revisions, dimensions, or transforms.

No vector index is created for the initial small corpus. Oracle performs an
exact cosine scan inside the already-authorised scope and applies `FETCH EXACT`
before returning the bounded union. Introduce an Oracle cosine vector index
only after representative corpus growth makes measured authorised-query p95
latency miss its budget; that change must compare exact versus approximate
recall on the behavioural suite, preserve active-profile filtering, and be a
separately reversible Liquibase change.

## Prompt Boundary

Selected local chunks are JSON-encoded beneath `LOCAL KNOWLEDGE EVIDENCE
(UNTRUSTED DATA)`. They are reference data, never system instructions. The
prompt tells the model to ignore commands, role changes, secret requests, and
other prompt injection found inside documents. It also states that bounded
excerpts are non-exhaustive, that omission from them is not evidence of absence
from a document or corpus, and that mention is not attribution. For bounded
local-knowledge answers, a deterministic response policy rewrites only
categorical unsupported collection-absence claims before streaming,
persistence, response envelopes, or TTS. Existing system policy,
personality, generation presets, history budgeting, reasoning-tag handling,
streaming, and response persistence remain in place.

## Provenance And Diagnostics

Assistant message metadata and response metadata may record:

- route type and retrieval outcome;
- safe reason codes;
- canonical scope;
- source-object, document, document-version, and selected chunk identifiers;
- candidate, threshold, selected, malformed-row, model, and timing diagnostics
  in structured logs.

Provenance does not contain chunk text, vectors, processing instructions,
credentials, unrestricted prompts, or full documents.

Expected outcomes include `grounded`, `no_evidence`, `retrieval_failed`, scope
denial/unavailability, model incompatibility, and candidate-limit failure.
For an explicit knowledge route, denial, unavailability, no evidence, and
retrieval failure are terminal and do not execute a plugin or generate an LLM
answer. Denied/unavailable provenance contains only the Core source, terminal
route/outcome, and safe reason codes. Combined local and internet evidence
remains a later phase. P1-08 bounded same-document follow-ups remain unavailable
while their separate shipped setting
`[knowledge.model_evidence].follow_up_enabled=false` is unchanged.

## Acceptance Ingestion

Acceptance uses an enabled `DROP_BOX_ACCEPTANCE` location pointed at a
controlled inbox and leaves it enabled after the Core worker completes. The
retained location and corpus make the test reproducible. Verify the current
file SHA-256, non-test parent reference, canonical scope, completed request,
current document version, chunks, native vectors, immutable profile/digest,
model shape, processing profile, classification tags, and provenance through
published views. The compatibility processing profile has no behavioural
authority. `hash-embedding-v1` is deterministic test-only legacy scaffolding
and is not accepted as production semantic knowledge retrieval.
