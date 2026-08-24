# P2-06 Secure Binary Materialisation Implementation Record

Date: 23-Aug-2026

Status: Implemented and validated behind a disabled feature flag

Source plan: `p2-06-secure-binary-materialisation-plan.md`

## Outcome

P2-06 now provides a Core-owned, fail-closed materialisation boundary for an
exact current P2-04 policy approval and P2-05 `SELECTED` or approved `FALLBACK`
route. The boundary re-authorises one registered artefact, verifies its managed
bytes from the opened descriptor, applies one separately reviewed deterministic
processor profile, and creates a private opaque single-use attachment.

The shipped feature remains disabled. The production processor registry is
empty and the default P2-05 route revalidator defers every request. Therefore
this implementation does not make any binary or specialist route eligible.
Positive execution is available only to injected deterministic processors and
route evidence, as exercised by isolated synthetic test fixtures.

No provider or model is invoked, listed, loaded, pulled, downloaded, probed, or
registered. No specialist adapter, route-selection engine, remote-processing
enablement, APEX administration, plugin attachment path, or P2-07 behaviour was
added.

## Route-authority clarification

P2-06 binds an attachment to the exact immutable P2-05 result it receives, but
does not define route authority or select a model. For a specialist result, the
controlled route identity is the capability-requirement identity. A future
P2-05 result may additionally contain the exact concrete provider/model and
evidence snapshot selected for that evaluation; those fields are eligibility
and invocation evidence, not part of the design-time route definition.

P2-07 must validate and bind that selected eligibility snapshot at consumption
and invocation time, either through the existing complete P2-05 result/evidence
fingerprint or a separately reviewed narrow contract extension. Changing the
selected model requires a new P2-05 result and a new independently authorised
P2-06 attachment. P2-06 must not discover, rank, substitute, or bless models.

## Implemented Core contracts

`src/orac_core/knowledge/binary_materialisation.py` defines immutable typed
contracts for:

- exact P2-04 policy identity, safety inspection, verified representation,
  independent MIME decision, selection, transformation chain, output
  representation, dimension-qualified limits, evaluation time, and expiry;
- exact P2-05 result identity, route kind and identity, deterministic processor
  profile, policy/selection/limit/evidence fingerprints, fallback position,
  locality/classification/consent/minimisation decision references, evaluation
  time, and expiry;
- registered document-version, extraction, artefact, byte-count, digest, and
  source fingerprints;
- request, correlation, audit, cancellation, expiry, and cleanup identities;
- `READY`, `DEFER`, and `REJECT` results with safe reason codes, opaque handle,
  fingerprints, representation/MIME evidence, output size/digest, applied
  limits, deterministic derivative provenance, timestamps, cleanup state, and
  bounded content-free audit fields.

The public request contract contains no path, storage key, URL, filename,
credential, provider payload, raw SQL, command, or content field. Logical
selection coordinates are controlled, finite, numeric, non-empty, and
inclusive-exclusive.

## Source authority and revalidation

`CoreBinarySourceResolver` reuses the existing Core retrieval API with an exact
`CONTENT`/`ARTEFACT`/`COMPLETE` request and current principal and RAG scope. It
requires one approved row and a complete output set, then verifies exact
document-version, extraction, artefact, MIME, byte-count, digest, and source
fingerprint agreement.

The internal storage key returned by the existing Core API never enters a
public request or result. It is passed only to `KnowledgeManagedStore`, whose
existing descriptor-oriented `open_verified` operation rejects malformed
logical identities, path traversal, symlinks, special files, unsafe ownership
or permissions, root replacement, size changes, digest changes, and changes to
the opened object during verification. The processor receives the same opened
and verified descriptor; P2-06 does not rediscover a pathname.

Immediately before byte access, the service:

1. verifies request, policy, route, safety, source, selection, and limit
   fingerprints;
2. requires current `ACCEPT` plus `SELECTED` or approved `FALLBACK` dispositions;
3. rejects expired or overlong approval/attachment lifetimes;
4. reapplies active, corrupt, encrypted, external-reference, nested-content,
   signature, structure, and expansion-risk gates;
5. requires an exact registered host-owned processor/profile/version;
6. applies a fresh injected P2-05 revalidation result whose route and policy
   fingerprints must match exactly;
7. re-authorises and revalidates registered source identity; and
8. verifies representation, MIME, safety measurements, and every required
   dimension before allocating an attachment.

## Limits and deterministic processor seam

Every approved profile automatically requires `BYTES`, `OUTPUT_BYTES`,
`RETRIES`, and `ELAPSED_TIME`, plus all family-specific dimensions declared by
that profile. Supported dimensions are `MEMBERS`, `EXPANDED_BYTES`, `OBJECTS`,
`PAGES`, `PIXELS`, `CELLS`, `DURATION`, `CHANNELS`, and `FRAMES`.

Missing required dimensions `DEFER`. Exceeded source, output, safety, or
expansion bounds `REJECT`. The host applies the smaller of approved and local
ceilings and fixes processor retries at zero. Source byte size is rejected
before processor inspection, output writes are bounded incrementally, and
cancellation and monotonic elapsed time are checked during processor work.

The seam deliberately supplies no deterministic processor implementation.
Every future processor profile requires separate review and must perform only
its declared deterministic inspection and selection. Cooperative terminal
checks are mandatory for in-process profiles; a processor that cannot provide
bounded interruption belongs behind a separately reviewed worker boundary in
later authorised work.

Deterministic derivative identity, output representation, exact processor
profile, authoritative status, and provenance fingerprint are retained in the
result. Spreadsheet and other deterministic outputs remain authoritative;
specialist interpretation cannot replace them.

## Opaque attachment lifecycle

`src/orac_core/knowledge/attachment_store.py` implements the attachment store:

- the host-owned runtime root and attachment directories are mode `0700`;
- payload and metadata objects are regular, single-link, owner-only mode `0600`;
- root device/inode, directory type, ownership, and permissions are fixed and
  rechecked through non-following descriptors;
- allocation uses a private temporary directory and atomic rename;
- handles are 256-bit random opaque base64url identities and encode no locator;
- content-free metadata binds the handle to exact request, principal, route,
  policy, source, selection, limits, processor/profile, decisions, correlation,
  audit, expiry, and cleanup identities;
- payload size and digest are recomputed from the descriptor opened for the one
  controlled consumer;
- state is atomically marked consumed before yielding that descriptor;
- success, consumer failure, cancellation, expiry, materialisation failure,
  timeout, shutdown, and startup reconciliation have bounded cleanup paths;
- repeated cleanup is safe, and consumed handles cannot be re-materialised as
  ready; and
- reconciliation only recovers or removes exact owner-controlled layouts below
  the fixed root. Unknown, unsafe, unowned, malformed, or ambiguous entries are
  reported and retained.

No physical path or managed-store key is returned by the service. Consumers
open an already bound descriptor through the service and cannot submit or
rediscover an attachment path.

## Runtime integration

The controller loads `[knowledge.binary_materialisation]` independently of the
Phase 1 prompt-only path. The shipped value is `enabled=false`, so no attachment
runtime directory is created by normal startup. If explicitly enabled, startup
constructs the service with an empty processor registry and the fail-closed
route revalidator, then performs bounded reconciliation. Controller shutdown
performs bounded cleanup of current live handles.

This configuration alone cannot enable materialisation. An exact reviewed
P2-05 revalidator and processor profile must be registered in code by later
separately authorised work.

## Database inspection and persistence decision

The required read-only inspection attempted saved connection `orac-service`
first. SQLcl reported `Connection not found: orac-service`, so the bounded
`orac-db` fallback was used and disconnected after aggregate/metadata queries.
No content, source path, managed key, filename, prompt, credential, provider
payload, reply, or model list was selected.

Inspection confirmed:

- artefact, extraction, document-version, output-set, hash, size, and MIME
  identity contracts are present and validated;
- 60 artefacts had no null required identity, duplicate role/logical identity,
  or incomplete output set in the bounded aggregate checks;
- the authorised retrieval API package spec and body are valid;
- current runtime has `EXECUTE` on the Core retrieval API and no direct Core
  knowledge-table grant was found for runtime, APEX, or plugin schemas;
- six provider-input declarations and two implemented text inputs exist, but no
  positive concrete-model evidence or provider/model input limits exist; and
- no production binary or specialist route is eligible.

The existing retrieval decision/outcome audit identity and the bounded P2-06
result/attachment metadata are sufficient for this stage. No new persistence,
controller, changelog, rollback, or grant was justified, so no database object,
row, privilege, or deployment was changed. P2-06 does not claim the complete
P2-08 provider-submission audit.

## Validation

Offline validation covers:

- P2-05 `DEFER`/`REJECT`, approved fallback, stale approvals, route
  revalidation, changed source identity, incomplete authority, and binding
  conflicts;
- absence of caller locators/payloads and rejection of invalid coordinates;
- managed-store digest, size, permission, symlink, descriptor/TOCTOU, and root
  controls;
- independent representation/MIME revalidation;
- corrupt, encrypted, active, external, nested, and expansion-risk denial
  before attachment allocation;
- all global and family-specific dimensions, output limits, cancellation, and
  elapsed-time cleanup;
- opaque/private/principal-request-route-bound/expiring/single-use handles;
- concurrent retry idempotency, startup recovery, ambiguous-entry retention,
  shutdown, and deterministic authoritative provenance; and
- continued Phase 1 prompt-only and connector/model-submission behaviour.

The focused compatibility run passed 107 tests and 39 parameterised subtests.
Ruff, mypy, Python compilation, and Black checks passed. The repository suite
passed 1,462 tests, 925 parameterised subtests, and two skips with six unrelated
dirty-baseline failures explicitly deselected; the unfiltered run confirmed
those same six failures and no P2-06 failure.

## Remaining gates

P2-06 supplies the secure interface but does not enable a media family.
Production enablement remains blocked by:

- absence of an accepted P2-05 capability-eligibility/model-selection contract
  and a production-eligible result satisfying it;
- absence of reviewed representative fixtures and measured processor/output
  envelopes;
- absence of an approved deterministic processor profile or P2-05 runtime
  revalidator; and
- the separately authorised P2-07 adapter, consumer, and invocation work.

The next planning input is
`p2-07-specialist-model-adapters-plan.md`. It must not be treated as P2-07
implementation authorisation.
