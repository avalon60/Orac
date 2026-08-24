# Plan P2-07: Integrate Approved Specialist Model Adapters

Source plan:

`docs/pending_work/orac_document_materialisation_enhancements_plan.md`

Primary inputs:

- `docs/pending_work/p2-06-secure-binary-materialisation-implementation-record.md`
- `docs/pending_work/p2-05-capability-aware-routing-and-fallback-policy.md`
- `docs/pending_work/p2-04-media-type-processing-policy.md`
- `docs/pending_work/p2-03-controlled-model-provider-metadata.md`
- `docs/pending_work/p2-02-controlled-capability-taxonomy.md`
- `docs/pending_work/p2-01-binary-multimodal-use-case-catalogue.md`

## Planning constraint

This is a planning deliverable only. Do not modify repository files, database
objects or rows, configuration, providers, models, adapters, routes,
attachments, plugins, managed-store content, deployed services, or runtime
state while reviewing this plan.

Implement P2-07 only after explicit implementation authorisation and only for
a specifically approved use case, capability-requirement contract,
provider/protocol adapter boundary, representative fixture set, and measured
input/output envelope. A production concrete model is not a design-time adapter
or route prerequisite. It is required only before a real invocation can become
eligible, through a current P2-05 selection result backed by exact P2-03
evidence.

P2-07 consumes an already approved immutable P2-05 route and an already `READY`
P2-06 single-use attachment. It does not choose or widen a route, reinterpret
P2-04 policy, manufacture capability evidence, expose attachment paths, infer
sensitivity, enable remote processing, replace deterministic authority,
implement general tool execution, or claim the complete P2-08 audit.

Treat the current dirty working tree as the approved baseline and preserve
unrelated work.

### Authority, eligibility, selection, and audit distinction

- **Route authority:** an immutable versioned P2-05 requirement contract over
  capabilities, representation, independent MIME rules, behavioural-evidence
  maturity, output, limits, locality/data handling, and fallback invariants.
- **Model eligibility:** exact current P2-03 evidence showing that one
  configured provider/model revision satisfies the whole requirement contract.
- **Model selection:** deterministic P2-05 ordering chooses one eligible
  candidate and freezes its provider, model revision/digest, evidence,
  associations, observations, and limits in one immutable evaluation result.
- **Adapter authority:** an exact host-owned provider/protocol translation and
  validation implementation. The adapter is not registered to a model and
  cannot discover, rank, substitute, or bless one.
- **Invocation/audit evidence:** P2-07 and P2-08 record the exact route
  requirement, selected provider/model/evidence snapshot, adapter, attachment,
  limits, attempt, and result used for every real invocation.

Synthetic model/evidence identities and a fake provider may validate these
contracts offline. They never authorise a real provider call.

## 1. Resolved evidence

- P2-03 provides controlled provider, input, model-evidence, representation,
  MIME, capability, and dimension-qualified limit structures.
- Current database evidence has no positive concrete-model capability or input
  limit suitable for a production specialist route.
- P2-04 owns verified representation, independent MIME decision, processing
  chain, exact selection, safety decisions, required output, and limits.
- P2-05 owns capability-based route authority, concrete-model eligibility,
  deterministic candidate selection, the frozen provider/model/evidence
  snapshot, locality/classification/consent/minimisation decisions, ordered
  fallback, and all non-widening invariants.
- P2-06 owns source re-authorisation, managed-byte verification, deterministic
  selection/transformation, opaque attachment allocation, exact binding,
  single controlled open, expiry, consumption, cleanup, and recovery.
- P2-06 ships disabled, with no production processor profile and a default
  route revalidator that defers every route. P2-07 cannot create its own P2-06
  handle or use a caller path, key, URL, filename, credential, or payload.
- Phase 1 primary-text submission remains prompt-only and must not acquire a
  binary argument as an incidental part of P2-07.
- Deterministic spreadsheet, extraction, and normalised evidence remains the
  factual authority. Specialist output is attributed optional evidence.

## 2. Objectives

P2-07 must:

1. Admit only one exact current `SPECIALIST_MODEL` P2-05 result whose route
   requirement is complete and whose runtime-selected configured model has
   complete current positive P2-03 evidence and limits satisfying it.
2. Consume one exact `READY` P2-06 attachment through the controlled
   single-use descriptor boundary, without receiving or rediscovering a path.
3. Bind the adapter call to the immutable request, principal, route, policy,
   source, selection, limits, locality/classification, consent, minimisation,
   and attachment fingerprints.
4. Translate the verified attachment into the narrow documented
   provider/protocol request shape without model-specific adapter registration
   or provider-native payload injection.
5. Enforce provider/model input, output, elapsed-time, retry, concurrency,
   locality, classification, consent, and minimisation limits without widening
   P2-04, P2-05, or P2-06 authority.
6. Treat all specialist output as untrusted, attributed, bounded,
   non-authoritative evidence unless the approved use case explicitly defines
   a narrower deterministic result contract.
7. Preserve deterministic output authority and an explicit link to the exact
   source selection and processor provenance.
8. Fail closed before invocation if evidence, health, limits, credentials,
   locality, classification, attachment binding, or cancellation is missing or
   stale.
9. Guarantee attachment terminalisation and bounded cleanup on success,
   rejection, provider failure, retry exhaustion, cancellation, timeout, and
   process shutdown.
10. Produce content-free correlation fields sufficient for later P2-08 without
    claiming P2-08 completion.

## 3. Required repository inspection

Inspect at least:

- the implemented P2-06 immutable contracts, default fail-closed registry,
  descriptor-only consumer, attachment state transitions, cleanup, recovery,
  configuration, controller startup, and tests;
- P2-05 capability-requirement identity, candidate-eligibility rules,
  deterministic model-selection snapshot, observation freshness,
  locality/classification/consent/minimisation references, fallback chain,
  health/cost/quality evidence, and side-effect boundary;
- P2-04 representation, MIME, selection, safety, transformation, required
  output, limit, and reason-code contracts;
- P2-03 API projections and grants for provider input, concrete model evidence,
  accepted representation/MIME, limits, implementation status, and evidence
  validity;
- every current connector/provider protocol call shape, cancellation mechanism,
  timeout, retry, streaming, response-size, logging, and exception-redaction
  boundary without invoking, listing, loading, pulling, downloading, probing,
  or registering a model;
- controller request lifecycle, cancellation, shutdown, service recovery,
  concurrency, and provider health ownership;
- configuration and secret ownership, ensuring credentials remain in the
  existing host-owned secret boundary and never enter P2-05/P2-06 contracts;
- plugin execution and resource boundaries so no plugin path, resource
  resolver, ranking, or manifest can become attachment or adapter authority;
- applicable AGENTS, context, database, security, Python, shell,
  documentation, generated-code, plugin, and Git guardrails; and
- existing managed-store, P2-04, P2-05, P2-06, connector, cancellation,
  fallback, model-submission, security, and provider-error tests.

Do not inspect real document content, prompts, filenames, physical source
paths, managed keys, credentials, provider payloads, provider replies, or
provider model lists during planning.

## 4. Required read-only database inspection

Use `orac-service` first. If unavailable, record that fact before using the
bounded `orac-db` fallback.

Confirm without content selection or provider activity:

- the P2-03 provider-input, representation, MIME, implementation-status, and
  provider-limit structures required by the first provider/protocol adapter;
- the P2-05 capability-requirement and deterministic candidate-selection
  contracts, using synthetic candidate/model/evidence identities during
  planning or offline tests;
- for real invocation enablement only, the exact P2-03 concrete-model evidence,
  capability, model-input, evidence-validity, and dimension-qualified limit
  rows selected by P2-05;
- the absence of wildcard, inferred, `UNKNOWN`, legacy-default, or
  provider-family evidence in the positive route;
- locality/classification/consent/minimisation authority and whether every
  reference is current and relationally valid;
- existing runtime/API grants and the absence of direct Core-table,
  managed-store locator, or credential exposure;
- existing audit identities suitable for P2-07 correlation and the gap left
  intentionally for P2-08; and
- controller, upgrade, rollback, and least-privilege reachability if new
  persistence is proposed.

Do not update rows, invoke inference, list/load/download/pull/probe/register a
model, access managed content, deploy database objects, or call a provider
during planning.

## 5. Adapter admission contract

Inputs must include:

- immutable P2-07 request, correlation, cancellation, and bounded audit
  identities;
- exact current P2-05 result identity, version, fingerprint, disposition,
  route kind, capability-requirement identity/version/fingerprint, fallback
  chain/step, evaluation time, expiry, and all evidence/decision references;
- the exact runtime-selected P2-03 provider, provider-input, `llm_id`, immutable
  model revision/digest, model-evidence, capability, model-input,
  representation/MIME, implementation, observation, and limit identities;
- exact P2-04 policy and selection fingerprints, verified representation,
  independent MIME decision, required capability set, output contract,
  deterministic provenance, and applicable limits;
- exact P2-06 result identity, opaque attachment identity, request/route/
  policy/source/selection/limit fingerprints, output size/digest,
  representation/MIME decision, created/expiry state, and derivative
  provenance;
- principal binding and current source-authorisation reference;
- locality, classification, consent, minimisation, and remote-processing
  decision references; and
- host deadline and cancellation state.

Inputs must not include caller-supplied paths, storage keys, filenames,
arbitrary URLs, credentials, access tokens, provider-native request fragments,
raw SQL, commands, tool definitions, unbounded coordinates, document content,
or an already opened transferable file object.

The adapter registry must use an exact controlled key such as:

```text
(provider_id, provider_input_id, protocol_code, protocol_version,
 adapter_code, adapter_version, request_schema_version)
```

Concrete-model, model-evidence, route, use-case, and attachment identities are
runtime admission inputs and must not be adapter-registry keys. Family-level,
provider-default, MIME-only, fuzzy, wildcard, alias, or unversioned adapter
matching is forbidden. The selected model is passed only as the exact
controlled identity frozen by P2-05; the adapter cannot replace or normalise it
to another alias.

## 6. Adapter output contract

Return only:

- disposition: `COMPLETED`, `DEFER`, `REJECT`, `CANCELLED`, or `FAILED`;
- stable safe reason code;
- P2-07 request/correlation/audit identities;
- exact route-requirement, policy, source, selection, attachment,
  provider-input, selected provider/model revision, concrete-model evidence,
  adapter/protocol, and capability fingerprints;
- attributed specialist result identity and bounded output representation;
- output byte/token/object counts and applied limits;
- provider request/response correlation fingerprints that contain no content,
  credential, URL, path, model reply, or raw provider identifier beyond the
  controlled metadata identity;
- start, first-byte if applicable, completion, cancellation, timeout, and
  attachment-consumption timestamps;
- retry count and terminal fallback eligibility code; and
- attachment cleanup outcome.

Do not return a provider-native response object, credential, request body,
physical path, managed key, raw attachment, unrestricted headers, raw error,
stack trace, or unbounded provider output.

## 7. Required lifecycle

1. Validate immutable P2-04, P2-05, P2-06, and P2-07 fingerprints and expiry.
2. Require `P205RouteKind.SPECIALIST_MODEL`, one complete immutable
   capability-requirement contract, and an exact eligible P2-05-selected or
   approved-fallback candidate snapshot; deterministic-only and Phase 1 routes
   `DEFER`.
3. Re-authorise the principal and exact registered source identity without
   accessing bytes.
4. Re-read the exact P2-03 provider/model evidence selected by P2-05,
   implementation status, capability/model-input associations,
   representation/MIME acceptance, limits, and validity through the approved
   API boundary, and prove that it still satisfies the unchanged requirement
   fingerprint.
5. Revalidate P2-05 locality, classification, consent, minimisation, health,
   cost/quality, observation freshness, and fallback position immediately
   before the side-effect boundary.
6. Resolve one exact host-owned provider/protocol adapter registration that is
   independent of concrete-model identity. Missing, ambiguous,
   version-mismatched, wildcard, disabled, or model-keyed registrations
   `DEFER`.
7. Resolve credentials through the existing host-owned secret boundary only;
   missing or invalid credentials fail before attachment consumption.
8. Reserve bounded concurrency and establish hard elapsed-time, input, output,
   retry, and cancellation ceilings before attachment consumption.
9. Open the exact P2-06 opaque handle once with the same principal/request/
   route/policy/source/selection binding. Never obtain its pathname.
10. Build the provider request exclusively from controlled adapter code,
    controlled metadata, verified representation/MIME evidence, and the
    descriptor stream under the approved byte bound.
11. Invoke once using exactly the model identity frozen by P2-05. A retry is
    permitted only when P2-05 and the provider-input
    limit explicitly allow it, no provider output was accepted, the same
    immutable requirement and selected candidate remain current, the request is
    idempotent at the provider boundary, and a new separately authorised P2-06
    handle is obtained. A consumed handle is never reused. Selection of a
    different eligible candidate is fallback, not retry: it requires a fresh
    P2-05 result and a separately authorised P2-06 handle.
12. Bound and validate response transport, media type/schema, size, tokens,
    object count, completion state, and attribution before accepting output.
13. Mark specialist output untrusted and non-authoritative, link it to exact
    deterministic provenance, and preserve any deterministic result as the
    primary authority.
14. Terminalise the attachment and clean it on success, rejection, provider
    failure, cancellation, timeout, protocol error, or response-validation
    failure.
15. Return only bounded safe result metadata and one explicit fallback
    eligibility reason to the P2-05 owner. P2-07 itself does not select the next
    route.

No lifecycle stage may execute document active content, follow embedded or
external references, acquire remote document content, accept provider-request
instructions from document content, widen a selection, or turn plugin paths or
provider output into attachment authority.

## 8. Provider request boundary

Every approved adapter must document and test:

- the exact provider input transport and representation;
- the exact protocol/request-schema versions and proof that adapter
  registration is independent of concrete-model identity;
- whether bytes are streamed, copied into a bounded SDK object, or sent through
  a descriptor-aware client;
- maximum source bytes, encoded bytes, multipart overhead, objects/pages/
  images/audio/video dimensions, output bytes/tokens, retries, elapsed time,
  and concurrency;
- the exact model-evidence identity and observation validity period;
- locality and data-retention behaviour, including whether any remote
  processing occurs;
- credential source and redaction behaviour;
- request idempotency and whether a safe retry can exist;
- cancellation behaviour when the client or provider cannot interrupt an
  in-flight call immediately;
- accepted response schema/media types and bounded parsing behaviour; and
- safe provider-error mapping with no raw response, headers, endpoint,
  credential, content, or stack trace.

Provider SDK convenience methods that require a caller pathname are not
eligible. An adapter may copy from the controlled P2-06 descriptor into a
bounded in-memory or SDK-owned request object only when the exact P2-04/P2-05
and host byte ceilings permit it and the copy has bounded cancellation and
cleanup.

## 9. Limits and fallback

P2-07 must enforce the smaller of:

- P2-04 media/selection/processing limits;
- P2-05 capability-requirement, selected provider/model, locality,
  cost/quality, retry, and observation limits;
- P2-06 verified attachment size, representation, selection, expiry, and
  cleanup limits;
- exact P2-03 provider/model input and output limits; and
- stricter host/adapter ceilings.

Unknown required limits or evidence `DEFER`. Safety, locality,
classification, consent, minimisation, attachment, response-schema, or hard
limit violations `REJECT`. Provider unavailability, bounded transient failure,
or expired observation may return a safe fallback-eligible `DEFER` only when
P2-05 explicitly permits that transition.

P2-07 cannot reorder candidates, skip fallback steps, replace deterministic
authority, increase retries, create a broader selection, switch provider/model
identity, or silently fall back to remote processing. Every retry requires a
fresh route revalidation and a new single-use attachment.

An alternate configured model may be used only after P2-05 evaluates it against
the same or explicitly ordered equivalent capability requirement, selects it
deterministically, and issues a new immutable result. P2-07 never performs this
selection inside the adapter.

## 10. Stable reason-code families

Define safe stable codes covering at least:

- invalid, stale, mismatched, non-specialist, or non-eligible route;
- incomplete or mismatched capability-requirement contract, no eligible
  configured model, ambiguous deterministic selection, or selected-candidate
  snapshot mismatch;
- missing/stale provider, provider-input, model, capability, representation,
  MIME, implementation, observation, or limit evidence;
- locality, classification, consent, minimisation, or remote-processing denial;
- adapter missing, ambiguous, disabled, incompatible, or version-mismatched;
- credential unavailable without revealing credential type or source;
- attachment missing, stale, expired, consumed, binding-mismatched, changed,
  cancelled, or cleanup-failed;
- request encoding, bounded copy, transport, protocol, response-schema,
  response-media, output-limit, and attribution failures;
- provider unavailable, rate-limited, timeout, cancelled, retry-exhausted, or
  non-idempotent retry denial;
- deterministic-authority/provenance mismatch; and
- audit-correlation or terminal-state failure.

Errors must not expose content, filenames, physical paths, managed keys,
arbitrary URLs, credentials, provider-native identifiers, endpoints, raw
headers, raw tool output, provider replies, model lists, or stack traces.

## 11. Concurrency, cancellation, and recovery

- Use immutable request/route-requirement/selected-candidate/policy/source/
  selection/attachment/adapter fingerprints for idempotency and cross-binding
  denial.
- Never hold a database transaction across attachment consumption or provider
  I/O.
- Reserve concurrency before consuming the single-use attachment.
- Treat cancellation as terminal for the attachment even if the provider call
  cannot be interrupted immediately; discard and bound any late result.
- Do not retry after any accepted provider output or with the same attachment.
- Persist nothing unless a reviewed P2-08-compatible need cannot be met by the
  existing audit boundary and minimal P2-07 correlation fields.
- On startup or shutdown, P2-07 may ask P2-06 to reconcile its own attachments;
  P2-07 must not scan, name, open, or delete runtime files itself.
- Ambiguous provider or attachment state fails closed and is reported without
  destructive recovery.

## 12. Audit and provenance boundary

Record content-free correlation for request, principal, source/artefact,
extraction/output set, deterministic evidence, P2-04 policy, P2-05
capability-requirement and selection decisions, P2-06 attachment lifecycle,
the exact runtime-selected P2-03 provider/`llm_id`/revision/model evidence,
adapter/protocol, capabilities, limits, attempt count, timestamps, disposition,
safe reason, fallback eligibility, and cleanup outcome.

Do not store prompt/document content, raw attachment bytes, provider request or
response bodies, credentials, paths, managed keys, arbitrary URLs, raw headers,
or raw exceptions.

P2-07 must explicitly identify which timing, provider request/response,
fallback-outcome, cost/usage, retention, and operational fields remain for
P2-08. It must not claim complete submission audit or observability.

## 13. Deliverables after authorisation

Produce:

- a standalone P2-07 implementation record under `docs/pending_work`;
- immutable adapter request/result/registry contracts in the Core knowledge
  boundary;
- one exact approved provider/protocol specialist adapter, independent of
  concrete-model identity, after the requirement-contract and fixture gates are
  satisfied;
- fail-closed capability-requirement, selected provider/model evidence, and
  route revalidation immediately before any real invocation;
- descriptor-only consumption of the P2-06 single-use handle;
- bounded request translation, invocation, response validation, cancellation,
  timeout, concurrency, retry, cleanup, attribution, and deterministic
  provenance controls;
- minimal persistence only through documented Core/API/Code topology, with
  exact controller, upgrade, rollback, and least-privilege grants if approved;
- offline unit/security/contract tests using a fake provider and isolated P2-06
  roots, plus rollback-only database acceptance if database objects change;
- operator/user documentation only for functionality actually enabled;
- a master-plan update after validation; and
- a standalone P2-08 audit and observability plan.

Do not add a general provider router, model discovery, model pull/load/probe,
unapproved adapter, plugin attachment path, direct provider-native payload API,
remote enablement, sensitivity inference, APEX administration, or P2-08
implementation.

## 14. Tests

Tests must prove:

- non-specialist, `DEFER`, `REJECT`, stale, widened, or fingerprint-mismatched
  P2-05 results cannot invoke;
- absent, stale, inferred, wildcard, provider-family, unimplemented, or limit-
  incomplete P2-03 evidence cannot invoke;
- two synthetic configured model identities satisfying one immutable
  capability-requirement contract are independently eligible, deterministic
  P2-05 ordering selects exactly one, and the route identity does not change;
- model identity or evidence is never an adapter-registry key, while the exact
  selected provider/model/evidence snapshot is mandatory invocation and audit
  evidence;
- no eligible configured model produces `DEFER` without changing or weakening
  the route requirement;
- changed authorisation, source, P2-04 policy, selection, representation, MIME,
  deterministic provenance, locality, classification, consent, or minimisation
  cannot invoke;
- caller paths, keys, URLs, filenames, credentials, provider payload fragments,
  commands, and unbounded coordinates are rejected;
- only the exact P2-06 handle can be consumed and it cannot cross principal,
  request, route, policy, source, selection, provider, adapter, or attempt;
- expired, cancelled, already consumed, changed, unsafe, or cleanup-ambiguous
  handles never reach the provider;
- request translation uses only the exact controlled adapter schema and never
  executes or dereferences document content;
- every applicable input/output/encoded-size/object/page/pixel/cell/duration/
  channel/frame/token/retry/elapsed-time/concurrency limit is enforced without
  widening;
- response size, schema, media type, completion, and attribution are bounded
  before acceptance;
- deterministic spreadsheet and normalised results remain authoritative and
  specialist results remain attributed untrusted evidence;
- cancellation, timeout, provider failure, malformed response, retry denial,
  retry exhaustion, and late results terminalise and clean the attachment;
- a retry, when explicitly permitted, revalidates the same route and obtains a
  new P2-06 handle rather than reusing one;
- logs, results, and audit fields contain no content, path, key, credential,
  endpoint, raw headers, provider payload/reply, stack trace, or model list;
- no model is listed, loaded, pulled, downloaded, probed, registered, or
  invoked outside the fake adapter fixture; and
- Phase 1 prompt-only behaviour and P2-06 deterministic-fixture behaviour
  remain unchanged.

Tests must use synthetic approved fixtures, a fake provider transport, fake
credentials, isolated temporary roots, and deterministic time/cancellation.
They must require no network, provider state, inference, mutable development
database, or real managed document content.

## 15. Implementation sequence after authorisation

1. Select exactly one approved P2-01 use case and record owner and acceptance
   evidence.
2. Finalise and approve the capability-eligibility and deterministic
   model-selection evidence contract, including route-requirement identity,
   candidate enumeration from configured metadata only, eligibility proof,
   ordering, frozen selection snapshot, and no-eligible-candidate outcome.
3. Validate that contract offline with at least two synthetic model identities,
   one ineligible synthetic identity, and a fake provider. This does not require
   or authorise a production model.
4. Before real invocation enablement only, reconfirm P2-03 positive evidence,
   exact limits, implementation status, and observation validity for at least
   one configured concrete model.
5. Reconfirm P2-04 policy and P2-05 specialist-route/non-widening contracts.
6. Reconfirm P2-06 single-use attachment contract and cleanup evidence.
7. Inventory the exact provider SDK/API call shape without provider activity.
8. Finalise immutable adapter registry, request, result, reason, limit,
   attribution, and terminal-state vocabularies.
9. Finalise credential, locality, retention, classification, consent,
   minimisation, concurrency, timeout, cancellation, and retry policy.
10. Implement requirement/selection evidence revalidation before the
    side-effect boundary.
11. Implement one exact provider/protocol adapter and descriptor-only request
    translation without model-keyed registration.
12. Implement bounded response validation and deterministic-authority linkage.
13. Integrate P2-06 consumption, terminal cleanup, late-result discard, and
    shutdown behaviour.
14. Add content-free correlation at the narrowest existing boundary.
15. Add offline fake-provider unit, security, concurrency, cancellation,
    timeout, retry, cleanup, and compatibility tests.
16. Add and validate minimal database changes only if separately approved and
    demonstrably necessary.
17. Update canonical documentation only for enabled behaviour.
18. Verify that no adapter-owned route selection, model discovery/probe,
    model-keyed adapter registration, unapproved
    provider, plugin attachment path, remote widening, or P2-08 implementation
    was added.
19. Update the master plan and produce P2-08 planning input using synthetic
    selection identities when production selection evidence is unavailable.

## 16. Acceptance criteria

P2-07 is complete when:

1. One explicitly approved specialist use case has a complete immutable
   capability-requirement contract, representative fixtures, measured envelope,
   and compatible P2-04/P2-05/P2-06 contracts. Offline contract completion does
   not require a production concrete model.
2. Only an exact eligible `SPECIALIST_MODEL` result can invoke; its selected
   concrete provider/model/evidence snapshot must satisfy the unchanged route
   requirement, while the registered adapter remains provider/protocol-based
   and model-independent.
3. The adapter consumes one exact P2-06 opaque handle without any path, key,
   URL, filename, credential, or provider-payload authority from the caller.
4. Re-authorisation, route/evidence/decision freshness, limits, attachment
   binding, and cancellation are checked immediately before invocation.
5. All request, response, retry, concurrency, output, and elapsed-time bounds
   fail closed without widening P2-04/P2-05/P2-06.
6. The attachment is terminal and cleaned on success, failure, cancellation,
   timeout, malformed response, retry transition, shutdown, and late result.
7. A consumed handle is never reused and every permitted retry obtains a new
   independently authorised handle.
8. Deterministic outputs remain authoritative with complete provenance;
   specialist output is bounded, attributed, and untrusted.
9. Safe errors and logs disclose no content, path, managed key, credential,
   endpoint, raw provider payload/reply, model list, or stack trace.
10. Phase 1 prompt-only behaviour and P2-06 fail-closed defaults remain
    compatible.
11. No model discovery, listing, loading, pulling, downloading, probing,
    registration, adapter-owned selection, or model-keyed adapter registration
    was added.
12. Offline tests and any approved rollback-only database acceptance pass.
13. The final activity produces a P2-08 plan without implementing P2-08.

## 17. In scope

- One exact approved provider/protocol specialist adapter and its
  model-independent immutable registry contract.
- Capability-requirement evaluation plus P2-03 selected-candidate evidence and
  P2-05 result revalidation before provider side effects.
- Descriptor-only P2-06 handle consumption and terminal cleanup.
- Bounded provider request translation and response validation.
- Locality, classification, consent, minimisation, credentials, concurrency,
  cancellation, timeout, retry, attribution, and deterministic provenance
  controls.
- Content-free correlation and offline fake-provider tests.
- Minimal approved database changes and documentation only when necessary.

## 18. Out of scope

- P2-04 media policy or P2-05 route-selection changes.
- P2-06 source/attachment authority changes except a separately reviewed defect
  fix required for the exact adapter contract.
- General adapter framework expansion or unapproved providers/use cases;
  adapters may serve any configured model selected by P2-05 when its exact
  evidence satisfies the adapter's provider/protocol input contract.
- Model listing, discovery, probing, loading, pulling, download, registration,
  or benchmark inference.
- Sensitivity inference or implicit remote-processing enablement.
- Direct caller/provider-native payloads or plugin-owned attachment handling.
- Active-content execution, external-reference acquisition, arbitrary tools,
  code execution, or document-supplied commands.
- APEX administration.
- P2-08 through P2-10 implementation.
- Unrelated dirty-tree work.

## 19. Assumptions and blockers

Assumptions:

- P2-03 controlled metadata, P2-04 policy, P2-05 route, and P2-06 attachment
  results remain immutable authoritative inputs.
- P2-05 route authority is capability-based; concrete-model evidence is
  eligibility evidence and the selected model is immutable runtime/audit
  evidence.
- Missing or stale evidence, decisions, limits, credentials, health, or
  attachment state fails closed.
- Deterministic evidence remains authoritative and specialist output remains
  attributed untrusted evidence.
- The first adapter can be tested fully with a fake provider before any
  authorised real-provider validation.

Genuine blockers:

- No accepted capability-eligibility and deterministic model-selection evidence
  contract currently bridges the P2-04 requirement, P2-03 candidates, P2-05
  result, P2-06 binding, and P2-07 admission boundary. This blocks P2-07 runtime
  implementation.
- No production specialist invocation is currently eligible because no
  configured concrete model has positive capability/input/limit evidence. This
  blocks real-provider enablement, but not offline P2-07 contract/adapter
  implementation with synthetic model identities and a fake provider, nor
  P2-08 planning and contract validation.
- No P2-01 use case has approved representative fixtures, owner, measured
  quality gain, processor/output envelopes, locality/classification/consent/
  minimisation decisions, or demonstrated normalisation insufficiency.
- Remote-processing and retention authority is unresolved for any remote
  provider.
- P2-06 has no production processor profile or production P2-05 revalidator.
- Complete provider request/response, cost/usage, timing, fallback-outcome, and
  operational observability remains P2-08 work.

## 20. Final activity

Return to:

`@orac_document_materialisation_enhancements_plan`

`thread://019ff810-7695-7282-84e4-5fce86936a56`

Produce a standalone, copy/paste-ready P2-08 plan for binary submission audit
and observability using the P2-05 requirement/selection, P2-06 attachment, and
P2-07 adapter/invocation contracts. P2-08 planning must not require an eligible
production concrete model: validate its contracts with synthetic provider,
model, evidence, route, adapter, attachment, attempt, and outcome identities plus
the fake provider. Real invocation audit must still record the exact selected
provider/model revision, model-evidence, capability, route requirement, and
adapter identities. Do not implement P2-08 during that planning activity.
