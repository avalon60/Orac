# Dialogue Routing

Normal Orac dialogue uses one core-owned routing sequence. Route selection does
not bypass plugin policy, retrieval policy, persistence, or prompt boundaries.

## Precedence

1. Explicit user route-selection controls, currently direct internet commands
   such as `Search the web for ...`.
2. Explicit knowledge-source syntax, including unknown names, which terminates
   as authorised retrieval, safe denial/unavailability, or clarification.
3. Scope-neutral explicit local-retrieval intent, which reserves the governed
   retrieval path without selecting or granting a scope.
4. Deterministic plugin interception from validated plugin metadata.
5. Authenticated, authorised, configured-alias local-knowledge retrieval.
6. Existing internet-retrieval policy and SearXNG routing.
7. Semantic plugin hints retained for compatibility.
8. Ordinary LLM response.

This deterministic routing sequence is separate from model-governed retrieval.
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

Local knowledge routing is deterministic. Orac does not use an LLM or semantic
similarity to decide whether a turn requests a local knowledge source. A turn
must match either the explicit grammar or the implicit alias-and-question
rules below. Matching is case-insensitive and may occur within a longer turn.
This route-selection grammar is distinct from the later Phase 2C semantic
domain match, which can require governed retrieval for an otherwise ordinary
question without selecting or granting a scope.

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

For example, `Search the knowledge base for plugin installation` asks the user
which authorised scope to use because the turn does not name one.

Drop Box location codes and display names are not automatically dialogue
aliases. For example, `ORAC_DOCS` is usable as `<source-name>` only when it has
been added to `scope_aliases_json`; the location's configured target scope does
not create an alias by itself.

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

This signal cannot select a scope, create authority, or override an explicit
internet route. When it reaches governed retrieval, Orac requires a valid tool
call or returns retrieval as unavailable; model prose cannot satisfy the
requirement.

### Implicit Alias And Question

Without explicit knowledge-source syntax, a turn must contain both:

1. A configured scope alias as a complete phrase.
2. At least one of the following expressions:

```text
how | what | where | why | when | which
configure | configuration
document | documentation
guardrail
decision | decided
processing profile
```

Aliases are matched case-insensitively, longest first, and on whole phrase
boundaries. With the shipped aliases, these turns match:

```text
How do I configure a Drop Box processing profile?
What does the Orac documentation say about plugin installation?
```

`processing profile` remains an implicit-routing compatibility phrase for
historical dialogue. Current Drop Box administration uses Core-owned
classification tags and provenance-only ingestion notes; profiles do not
execute conversion or chunking behaviour.

These turns do not match implicit local knowledge routing:

```text
Tell me about Drop Box.       # alias present, no recognised expression
How are plugins installed?    # recognised expression, no scope alias
Give me an overview of Orac.  # alias present, no recognised expression
```

The current retrieval execution path requires one resolved scope. Name one
alias or canonical identity in a turn rather than relying on a multi-scope
request.

### Broad Document Intents

Within an authorised single-scope knowledge route, the explicit verbs
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

Matching either trigger selects a local knowledge route; it does not guarantee
that evidence will be returned. Orac then asks Oracle for the authenticated
user's RAG usage privilege and independently validates that the canonical
project or plugin scope is active,
and applies the lexical relevance threshold. A valid route with no qualifying
chunks terminates as `no_evidence` rather than falling through to general model
knowledge.

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

Configured scope data is checked at startup and revalidated per request through
a short-expiry cache. An expired cache is never served after a failed refresh.
Startup registry errors disable retrieval execution but keep routing active, so
explicit knowledge requests terminate as unavailable without plugin or LLM
execution and without exposing whether a requested corpus exists.

## Retrieval

The runtime reads current, completed chunks only through the definer-rights
`orac_code.knowledge_retrieval_api`. That package revalidates the authenticated
username, scope status, and current `USE` privilege before opening the bounded
cursor. The runtime has no direct searchable-view grant or synonym and never
loads stored vectors into Python. The package accepts one transient, validated
query vector for the active immutable profile and runs two independent,
scope-authorised branches:

- Oracle cosine-distance ranking over native `VECTOR(768,FLOAT32)`, admitted by
  the active profile's semantic threshold and `FETCH EXACT` candidate limit;
- lexical coverage for ordinary terms, exact identifiers containing `.`, `_`,
  or `-`, phrases, and source names, admitted independently at `0.25`.

The lexical threshold is not a universal hard gate. A strong paraphrase may
enter through the semantic branch with no lexical match, while exact names,
filenames, configuration properties, database objects, and versions remain
strong lexical candidates. Oracle returns only the union of at most 50 rows
from each branch, with raw semantic/lexical scores and deterministic ranks.
The host applies weighted reciprocal-rank fusion (`0.65` semantic, `0.35`
lexical, rank constant `60`) and then enforces selected-chunk, per-chunk,
total-context, and deduplication limits.

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
other prompt injection found inside documents. Existing system policy,
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
