# Plan P2-06: Implement Secure Binary Materialisation

Implementation status: completed and validated behind a disabled feature flag
on 23-Aug-2026. See
`p2-06-secure-binary-materialisation-implementation-record.md`. This file is
retained as the approved planning input and acceptance baseline.

Source plan:

`docs/pending_work/orac_document_materialisation_enhancements_plan.md`

Primary inputs:

- `docs/pending_work/p2-05-capability-aware-routing-and-fallback-policy.md`
- `docs/pending_work/p2-04-media-type-processing-policy.md`
- `docs/pending_work/p2-03-controlled-model-provider-metadata.md`
- `docs/pending_work/p2-02-controlled-capability-taxonomy.md`
- `docs/pending_work/p2-01-binary-multimodal-use-case-catalogue.md`

## Planning constraint

This is a planning deliverable only. Do not modify repository files, database
objects or rows, configuration, plugins, managed-store content, processors,
adapters, routes, attachments, temporary files, providers, models, or deployed
services while reviewing this plan.

Implement P2-06 only after explicit implementation authorisation.

P2-06 defines secure bounded materialisation of verified source bytes and
derived selections for an already approved P2-05 route. It does not choose a
route, weaken P2-04, implement a specialist processor/model, invoke a provider,
infer sensitivity, enable remote processing, or implement P2-07 behaviour.

For a specialist route, the P2-05 controlled route identity is the immutable
capability-requirement identity, not a blessed concrete model. Any exact
provider/model/evidence selection carried by the P2-05 result is a frozen
eligibility snapshot for that evaluation. P2-06 binds the whole result without
becoming model-selection authority; a different selected candidate requires a
new P2-05 result and a new attachment.

Treat the current dirty working tree as the approved baseline and preserve
unrelated work.

## 1. Resolved evidence

- The managed store is the only authority for immutable source bytes and uses
  logical registered identities rather than caller-supplied paths.
- Existing retrieval/materialisation revalidates authorisation, registered
  identity, size, hashes, complete output sets, selection coordinates, and
  normalised UTF-8 evidence.
- Phase 1 rejects raw binary materialisation and emits prompt strings only.
- P2-04 owns representation inspection, deterministic chains, selections,
  safety reasons, required outputs, and dimension-qualified bounds.
- P2-05 owns the capability-based route identity, exact candidate-eligibility
  selection snapshot, locality/classification decision references, fallback
  chain, and non-widening invariants.
- No binary/specialist route is currently eligible. P2-06 must not manufacture
  eligibility and may be exercised only with approved deterministic fixtures
  until positive route evidence exists.
- No caller may receive or supply a managed-store path, storage key, arbitrary
  URL, credential, or provider-native payload.

## 2. Objectives

P2-06 must:

1. Accept only an immutable current `SELECTED` or approved `FALLBACK` P2-05
   result and its exact bounded selection.
2. Revalidate principal, source identity, policy/route versions, hashes,
   selection, limits, locality/classification decisions, and expiry immediately
   before byte access.
3. Read source bytes only through the managed-store authority without path or
   symlink bypass.
4. Materialise only the representation and byte range required by the selected
   deterministic processor or adapter contract.
5. Use short-lived, private, bounded attachment handles that reveal no physical
   path or managed key to callers.
6. Prevent time-of-check/time-of-use substitution, active-content execution,
   unsafe archive expansion, unbounded decoding, and attachment reuse.
7. Guarantee bounded cleanup on success, failure, cancellation, timeout, and
   process recovery.
8. Preserve deterministic output authority and complete provenance.
9. Keep all provider/model invocation and specialist adapter work in P2-07.

## 3. Required repository inspection

Inspect at least:

- managed-store logical key validation, open/read APIs, hashing, promotion,
  temporary-file handling, reconciliation, symlink/type/permission checks, and
  root stability;
- knowledge artefact/output-set identity, retrieval authorisation, materialised
  selection, provenance, auditing, and Phase 1 raw-binary denial;
- P2-04 inspection/selection/representation/limit contracts and reason codes;
- P2-05 route identity, locality/classification references, fallback and
  side-effect boundaries;
- current connector/adaptor call shapes without invoking them;
- service cancellation, retry, timeout, startup recovery, and shutdown paths;
- configuration and secret ownership;
- plugin resource/runtime boundaries so plugin paths cannot become attachment
  inputs;
- applicable AGENTS, context, database, security, Python, shell,
  documentation, generated-code, plugin, and Git guardrails;
- existing managed-store, materialisation, reconciliation, connector, routing,
  and security tests.

Do not inspect document content, prompts, filenames, source paths, managed keys,
credentials, provider payloads, model replies, or provider model lists.

## 4. Required read-only database inspection

Use `orac-service` first. If unavailable, record that fact before using the
bounded `orac-db` fallback.

Confirm without content selection:

- artefact/output-set/extraction identity and hash/size contracts;
- authorisation and retrieval audit entrypoints;
- any raw source MIME/representation metadata and its authority;
- current P2-03/P2-05 route evidence and limit availability;
- existing runtime grants and absence of direct managed-store path exposure;
- database fields suitable for safe attachment lineage/audit identity;
- controller and rollback reachability if persistence is proposed.

Do not update rows, invoke inference, list/load/download models, access managed
content, or deploy objects during planning.

## 5. Materialisation input contract

Inputs must include:

- immutable P2-05 result identity, version, fingerprint and evaluation time;
- exact selected route kind and controlled route identity;
- P2-04 policy result identity and source-authorisation snapshot;
- registered source/artefact identity, extraction/output-set identity, expected
  byte count and digest;
- verified representation plus independent MIME decision;
- exact bounded logical selection and every applicable limit;
- deterministic transformation chain and required output representation;
- locality/classification/consent/minimisation decision references;
- request, correlation and audit identities;
- expiry, cancellation and cleanup deadline.

Inputs must not include caller-supplied paths, storage keys, arbitrary URLs,
credentials, provider payloads, raw SQL, commands, or unbounded coordinates.

## 6. Output and attachment-handle contract

Return only:

- disposition: `READY`, `DEFER`, or `REJECT`;
- safe reason code;
- single-use opaque attachment identity;
- route/policy/source/selection fingerprints;
- verified representation and MIME decision;
- byte count, digest and dimension-qualified bounds;
- deterministic derivative identities and provenance where applicable;
- created, expires and consumed timestamps;
- cleanup state and bounded audit fields.

The opaque handle must be unguessable, principal/route/request bound,
single-use, short-lived, non-transferable, and invalid after cancellation,
expiry, consumption, or cleanup. It must not encode or expose a path, managed
key, filename, credential, URL, or content.

## 7. Required lifecycle

1. Validate P2-05 disposition, immutable fingerprints and expiry.
2. Re-authorise the principal and registered source identity.
3. Reconcile declared MIME with verified representation/inspection evidence.
4. Reapply P2-04 safety gates and exact selection/bounds.
5. Open the registered source through the managed-store authority using a
   non-following, descriptor-oriented operation.
6. Verify object type, ownership/permissions, byte count and digest from the
   opened object before use.
7. Apply only the approved deterministic selection/transformation under hard
   input, expansion, output and elapsed-time ceilings.
8. Create a private mode-`0600` short-lived attachment object or an equivalent
   descriptor-backed handle in a host-owned runtime directory.
9. Atomically bind the handle to the exact route/request/principal and record
   content-free lineage/audit metadata.
10. Permit one controlled consumer to open the already verified object without
    rediscovering or substituting its path.
11. Mark consumed and clean up on completion, failure, cancellation or timeout.
12. Reconcile stale handles/files safely at startup without following links or
    deleting unowned/unrecognised entries.

No stage may execute active content, dereference external references, acquire
remote content, follow caller-controlled links, or widen the selection.

## 8. Limit contract

Every materialisation must enforce the P2-04/P2-05 dimensions applicable to
the family, including `BYTES`, `OUTPUT_BYTES`, `RETRIES`, `ELAPSED_TIME`, and
as applicable `MEMBERS`, `EXPANDED_BYTES`, `OBJECTS`, `PAGES`, `PIXELS`,
`CELLS`, `DURATION`, `CHANNELS`, and `FRAMES`.

P2-06 may apply a stricter host ceiling but cannot increase an approved limit.
Unknown required dimensions `DEFER`; exceeded safety/expansion dimensions
`REJECT`. Partial hidden-container expansion is not a safe fallback.

## 9. Failure and cleanup reason codes

Define stable safe reasons covering at least:

- invalid/stale route or policy identity;
- authorisation/source identity change;
- missing or changed registered bytes;
- representation/MIME mismatch;
- corrupt, encrypted, active, external, nested, or expansion-risk content;
- unknown or exceeded bounds;
- unsupported deterministic processor/profile;
- attachment allocation, permission, binding, expiry, consumption and cleanup
  failures;
- cancellation and elapsed-time expiry;
- reconciliation ambiguity.

Errors must not expose content, filenames, physical paths, managed keys,
credentials, provider details, or raw tool output.

## 10. Concurrency and recovery

- Use immutable request/route/source fingerprints for idempotency.
- Do not reuse a handle across principals, requests, routes or selections.
- Make promotion/binding atomic and make repeated cleanup safe.
- Hold no database transaction across long filesystem or processor work.
- Detect source replacement from the opened descriptor, not a prior pathname
  check.
- Treat cancellation as terminal for the handle even when an underlying
  processor cannot be interrupted immediately.
- Reconcile only host-owned, layout-valid, expired entries inside the exact
  configured runtime area; report ambiguous entries without deleting them.

## 11. Audit and provenance

Record content-free identities for request, principal, source/artefact,
extraction/output set, P2-04 policy, P2-05 route/evidence, selection, limits,
processor/profile, representation/MIME decision, attachment lifecycle,
digests/byte counts, timestamps, safe reason, and cleanup outcome.

Do not claim that P2-06 provides the complete P2-08 submission audit. Provider
request/response, selected specialist execution, timing and fallback outcome
belong to later authorised work.

## 12. Deliverables after authorisation

Produce:

- a standalone P2-06 implementation record under `docs/pending_work`;
- typed immutable materialisation/handle contracts in the Core knowledge
  boundary;
- deterministic validators and fail-closed lifecycle service;
- any minimal persistence only through the documented Core/API/Code topology;
- exact controller, upgrade, rollback and least-privilege grants if database
  objects are approved;
- private runtime-directory configuration and startup reconciliation;
- offline unit/security tests and rollback-only database acceptance where
  applicable;
- user/operator documentation only for functionality that becomes available;
- a master-plan update after validation;
- a standalone P2-07 specialist-adapter plan.

Do not add a provider/model invocation, specialist adapter, route-selection
engine, remote enablement, APEX administration, plugin attachment path, or
P2-07 implementation.

## 13. Tests

Tests must prove:

- P2-05 `DEFER`/`REJECT`, stale results and changed source identities cannot
  materialise;
- caller paths, keys, URLs, filenames and unbounded selections are rejected;
- symlink, special-file, permission, digest, size and TOCTOU substitution
  checks fail closed;
- representation and MIME are independently revalidated;
- encrypted, active, corrupt, external-reference and expansion-risk inputs do
  not produce attachments;
- every family enforces its dimension-qualified limits without widening;
- handles are opaque, principal/request/route bound, expiring and single-use;
- files/objects are private and cleanup covers success, failure, cancellation,
  timeout and restart;
- concurrent retries are idempotent and cannot cross-bind handles;
- deterministic spreadsheet results remain authoritative;
- no model is listed, loaded, pulled, downloaded, probed or invoked;
- no plugin path or ranking becomes attachment authority;
- Phase 1 prompt-only normalised behaviour remains unchanged.

Tests must use synthetic approved fixtures and isolated temporary roots. They
must require no network, provider state, inference, mutable development
database, or real managed document content.

## 14. Implementation sequence after authorisation

1. Reconfirm P2-04 and P2-05 contracts and current route evidence.
2. Inventory managed-store, retrieval, materialisation and cleanup boundaries.
3. Finalise immutable request/result/handle and safe-reason vocabularies.
4. Finalise runtime-directory ownership, permissions and recovery policy.
5. Implement source revalidation and descriptor-oriented verified reads.
6. Implement bounded deterministic selection/transformation seam.
7. Implement opaque single-use handle binding and lifecycle cleanup.
8. Add content-free audit/provenance at the narrowest existing boundary.
9. Add concurrency, cancellation, timeout and startup reconciliation.
10. Add offline unit, security and rollback-only database acceptance tests.
11. Update canonical documentation for any enabled operator/user behaviour.
12. Verify that no routing, provider invocation or P2-07 adapter was added.
13. Update the master plan and produce P2-07 planning input.

## 15. Acceptance criteria

P2-06 is complete when:

1. Only a current approved P2-05 route can materialise bytes.
2. Source authorisation, identity, digest, size, representation, selection and
   bounds are revalidated at use time.
3. No caller path/key/URL or symlink can select bytes.
4. Safety failures occur before attachment creation.
5. Every attachment is minimal, private, opaque, expiring and single-use.
6. All success/failure/cancellation/restart paths have bounded cleanup.
7. Fallback and materialisation cannot widen P2-04/P2-05 authority.
8. Deterministic outputs retain authority and provenance.
9. Audit fields are content-free and sufficient for later P2-08 correlation.
10. Phase 1 remains compatible.
11. No provider/model is invoked, listed, loaded, downloaded or probed.
12. Offline and database acceptance tests pass.
13. The final activity produces P2-07 without implementing it.

## 16. In scope

- Secure verified managed-byte access for an approved route.
- Bounded deterministic selection/transformation materialisation seam.
- Opaque short-lived attachment lifecycle.
- TOCTOU, permission, symlink, expansion, concurrency and cleanup controls.
- Content-free provenance and minimal audit linkage.
- Offline tests, approved database changes, documentation and rollout guards
  after implementation authorisation.

## 17. Out of scope

- P2-05 route selection or policy changes.
- Provider/model invocation and specialist adapters.
- Model listing, probing, loading, pulling, download or registration.
- Sensitivity inference or remote-processing enablement.
- New deterministic processor implementations beyond an approved seam.
- APEX administration or plugin-owned attachment handling.
- P2-07 through P2-10 implementation.
- Unrelated dirty-tree work.

## 18. Assumptions and blockers

Assumptions:

- P2-04 policy and P2-05 route results are immutable authoritative inputs.
- Managed-store registration, authorisation and hashes remain authoritative.
- Missing policy, evidence, selection or limit fails closed.
- Deterministic evidence remains authoritative.

Genuine blockers:

- No binary/specialist production route is currently eligible.
- Approved representative fixtures and measured processor/output envelopes are
  still required before enabling a family.
- Runtime-directory ownership and recovery semantics require explicit review
  before persistence or service integration.
- P2-07 cannot consume an attachment until P2-06 proves its exact single-use
  handle and cleanup contract.

## 19. Final activity

Return to:

`@orac_document_materialisation_enhancements_plan`

`thread://019ff810-7695-7282-84e4-5fce86936a56`

Produce a standalone, copy/paste-ready P2-07 plan for approved specialist model
adapters using the implemented P2-05 route and P2-06 attachment contracts. Do
not implement P2-07 during that planning activity.
