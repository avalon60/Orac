# Dialogue Routing

Normal Orac dialogue uses one core-owned routing sequence. Route selection does
not bypass plugin policy, retrieval policy, persistence, or prompt boundaries.

## Precedence

1. Explicit user route-selection controls, currently direct internet commands
   such as `Search the web for ...`.
2. Explicit knowledge-source syntax, including unknown names, which terminates
   as authorised retrieval, safe denial/unavailability, or clarification.
3. Deterministic plugin interception from validated plugin metadata.
4. Authenticated, authorised, configured-alias local-knowledge retrieval.
5. Existing internet-retrieval policy and SearXNG routing.
6. Semantic plugin hints retained for compatibility.
7. Ordinary LLM response.

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
Query the PLUGIN:drop_box knowledge base for processing profile guidance.
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

These turns do not match implicit local knowledge routing:

```text
Tell me about Drop Box.       # alias present, no recognised expression
How are plugins installed?    # recognised expression, no scope alias
Give me an overview of Orac.  # alias present, no recognised expression
```

The current retrieval execution path requires one resolved scope. Name one
alias or canonical identity in a turn rather than relying on a multi-scope
request.

### Triggering Versus Grounding

Matching either trigger selects a local knowledge route; it does not guarantee
that evidence will be returned. Orac then asks Oracle for the authenticated
user's RAG usage privilege and independently validates that the canonical
project or plugin scope is active,
and applies the lexical relevance threshold. A valid route with no qualifying
chunks terminates as `no_evidence` rather than falling through to general model
knowledge.

## Knowledge Scope

Dialogue retrieval is disabled by default under `[knowledge.dialogue]`.
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

`ORAC_CORE` is administrator-maintained and is not seeded from Drop Box
configuration. Before enabling dialogue retrieval, provision it through the
published maintenance boundary:

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

The first release reads current, completed chunks through
`orac_code.knowledge_searchable_chunks_v` and joins the approved ingestion
request view for processing-profile provenance. It requires the configured
embedding model identifier and dimensions to match stored chunks. The current
`hash-embedding-v1` provider is deterministic development/test infrastructure;
its cosine value is diagnostic, not a meaningful semantic relevance signal.

Lexical coverage is the first-release relevance gate. It recognises ordinary
tokens and exact technical identifiers containing `.`, `_`, or `-`, with small
phrase and source-name boosts. Generic route-control words and words already
represented by the resolved canonical scope are excluded from the query score;
they cannot turn an unrelated question into evidence. Rows below
`min_lexical_score` are excluded. Returning rows is not sufficient evidence by
itself. Retrieval also enforces a candidate cap, selected-chunk cap, per-chunk
character cap, total evidence cap, and content deduplication.

No native Oracle vector migration is part of this release. A production
embedding model and any native-vector change require a separate compatibility
and migration decision.

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
route/outcome, and safe reason codes. Combined local and internet evidence and
bounded follow-up routing are later phases.

## Acceptance Ingestion

Acceptance uses an enabled `DROP_BOX_ACCEPTANCE` location pointed at a
controlled inbox and leaves it enabled after the Core worker completes. The
retained location and corpus make the test reproducible. Verify the current
file SHA-256, non-test parent reference, canonical scope, completed request,
current document version, chunks, embeddings, model shape, processing profile,
and provenance through published views. The deterministic `hash-embedding-v1`
values prove shape and lifecycle only; lexical relevance is the actual
first-release selection gate.
