# Plan P2-05: Define Capability-Aware Routing and Fallback

Status: executed on 2026-08-23. The completed policy record is
[`p2-05-capability-aware-routing-and-fallback-policy.md`](p2-05-capability-aware-routing-and-fallback-policy.md).
No routing runtime was implemented.

Source plan:

`docs/pending_work/orac_document_materialisation_enhancements_plan.md`

Primary inputs:

- `docs/pending_work/p2-04-media-type-processing-policy.md`
- `docs/pending_work/p2-03-controlled-model-provider-metadata.md`
- `docs/pending_work/p2-02-controlled-capability-taxonomy.md`
- `docs/pending_work/p2-01-binary-multimodal-use-case-catalogue.md`

## Planning constraint

This is a planning deliverable only. Do not modify repository files, database
objects, metadata rows, MIME associations, providers, models, configuration,
plugins, managed-store content, processors, adapters, routes, or deployed
services while reviewing this plan.

Implement P2-05 only after explicit implementation authorisation.

P2-05 defines capability-aware eligibility, ordering, and fallback from an
approved P2-04 processing decision and P2-03 evidence. It does not implement
processors, attachments, provider/model invocation, model probing, sensitivity
classification, remote eligibility, health probes, cost collection,
administration UI, submission audit, or P2-06 behaviour.

Route authority is capability-based. A specialist route definition names a
versioned requirement contract--capabilities, representations, independent
MIME rules, behavioural-evidence maturity, dimensions and limits, locality and
data-handling constraints, and fallback invariants--and never requires one
concrete model. Concrete-model evidence is runtime eligibility input. The exact
provider/model/evidence selected for one evaluation is frozen in the result for
invocation and audit, but is not part of the design-time route identity.

Treat the current dirty working tree as the approved baseline and preserve
unrelated work.

## 1. Resolved evidence

P2-03 provides:

- exactly two reviewed adapters: `ollama` and `lmstudio`;
- separate provider transport and concrete-model behavioural evidence;
- absence-as-`UNASSESSED`;
- no current concrete-model capability evidence;
- representations and MIME as independent associations;
- dimension-qualified limits;
- provider locality metadata that is not remote permission;
- safe current-evidence projections that exclude expired rows.

P2-04 provides a provider/model-neutral processing result containing a
disposition, reason, deterministic chain, required/optional capabilities,
representations, MIME constraints, bounded selection, limits, fallback, and
unresolved policy/evidence requirements.

Current Phase 1 remains prompt-string-only and `TEXT`/`LOCAL`. Provider
image transport is `API_DECLARED` and adapter
`NOT_IMPLEMENTED`. No specialist route is operational.

## 2. Objectives

P2-05 must:

1. Define a model-neutral route-requirement contract and evaluate configured
   concrete models against it using positive evidence,
   representation/MIME compatibility, adapter support, bounds, and effective
   dates.
2. Keep provider transport necessary but insufficient for model behaviour.
3. Keep deterministic processors and specialist models distinct route kinds.
4. Define fail-closed locality and sensitivity gates without treating
   `DOC_CLASS` as sensitivity.
5. Define stable quality, cost, availability, and health inputs without
   inventing current values.
6. Define deterministic candidate ordering and tie-breaking.
7. Define fallbacks that preserve P2-04 authority and provenance.
8. Preserve the existing primary text model and Phase 1 path until later
   runtime authorisation.
9. Produce controlled input for P2-06 without implementing binary
   materialisation.

## 3. Required repository inspection

Inspect at least:

- implemented P2-03 tables, constraints, triggers, views, TAPIs, grants, seed,
  rollback, and controller reachability;
- completed P2-04 media defaults, overrides, chains, reason codes, selections,
  and bounds;
- P2-02 capability authority and representation contracts;
- P2-01 use cases and negative cases;
- current model/provider selection, connector construction, submission guards,
  retries, cancellation, and endpoint pinning;
- current configuration and feature-gate ownership;
- current knowledge retrieval/materialisation/model-submission provenance and
  audit contracts;
- plugin arbitration and execution boundaries, ensuring plugin ranking cannot
  become model routing authority;
- applicable AGENTS, context, database, security, Python, documentation,
  generated-code, plugin, and Git guardrails;
- existing routing, provider, materialisation, schema, and documentation tests.

Do not inspect document content, prompts, filenames, source paths, managed keys,
credentials, provider payloads, or model replies.

## 4. Required read-only database inspection

Use `orac-service` first. If unavailable, record that fact before using the
bounded `orac-db` fallback.

Confirm without content selection:

- P2-03 object status and current seed counts;
- current provider transport declarations and adapter-support states;
- current and expired concrete-model evidence counts by state;
- current representation/MIME and limit associations;
- registry/provider referential integrity and duplicate counts;
- available locality, classification, quality, cost, availability, and health
  metadata;
- existing consumers and grants for routing-relevant views;
- whether any source maps MIME directly to provider/model;
- whether any configured provider can download/load a model as a side effect.

Do not update rows, invoke inference, list provider models, load/download
models, probe endpoints, or access managed content.

## 5. Routing inputs and output

Inputs must include:

- immutable P2-04 policy result and version;
- required and optional capability codes;
- deterministic or specialist route kind;
- required representations and optional MIME constraints;
- bounded selection and dimension-qualified limits;
- immutable capability-requirement identity, version, fingerprint, and minimum
  acceptable behavioural-evidence maturity;
- the bounded set of configured candidate identities plus their current
  concrete-model evidence, model-input associations, provider transport, and
  adapter-support state;
- effective dates;
- explicit sensitivity/locality decision when applicable;
- approved quality, cost, availability, and health observations;
- request/route policy version and evaluation timestamp.

Output must contain:

- disposition: `SELECTED`, `FALLBACK`, `DEFER`, or `REJECT`;
- safe reason code;
- selected route-kind and capability-requirement identities;
- selected deterministic processor identity or an exact runtime
  provider/`llm_id`/revision/evidence eligibility snapshot;
- required evidence and transport association identities;
- satisfied and unresolved capability codes;
- representation/MIME decision;
- applied limits and bounded selection;
- fallback chain identity;
- policy/evidence fingerprints;
- locality/classification decision references;
- safe audit fields.

It must not contain prompts, document content, filenames, paths, managed keys,
credentials, arbitrary URLs, raw provider metadata, or unbounded payloads.

## 6. Eligibility gates

Evaluate in this order:

1. P2-04 disposition is `ACCEPT`; `REJECT` remains final and
   `DEFER` cannot route.
2. Source identity, authorisation, policy version, selection, and bounds remain
   current.
3. Every required capability is satisfied by the intended route kind.
4. Deterministic routes have a reviewed processor/profile and version.
5. Specialist route authority is complete without a concrete model; each
   configured candidate is independently eligible only when it has current
   positive evidence satisfying every requirement. Absence is `UNASSESSED` and
   makes that candidate, not the route contract, ineligible.
6. Provider transport is `API_DECLARED`, adapter status is
   `IMPLEMENTED`, and representation/MIME is compatible.
7. Evidence and associations are effective and not expired.
8. All provider/model/processor limits cover the selection.
9. Sensitivity and locality policy explicitly permits the route. Missing policy
   fails closed.
10. Availability and health observations are current enough for the route.
11. Cost and quality rules are satisfied where approved.
12. The requirement contract, exact selected candidate/evidence snapshot, and
    fallback chain are auditable and deterministic.

`API_DECLARED`, provider locality, `TEXT`, MIME presence, enabled registry
state, or health alone cannot satisfy behavioural eligibility.

## 7. Candidate ordering

Define one stable lexicographic ordering after eligibility:

1. authoritative deterministic processor when the P2-04 chain requires
   inspection, extraction, calculation, rendering, or selection;
2. policy-required locality;
3. stronger current evidence maturity;
4. approved suitability/quality tier;
5. approved cost class;
6. current availability/health class;
7. explicit administration priority;
8. stable candidate identity as the final deterministic tie-break.

Do not use install order, filesystem order, registry row order, first match,
embedding similarity, model output, or provider-owned ranking as final
authority.

Quality, cost, health, and priority vocabularies must be separately controlled.
Do not overload evidence maturity or `is_enabled`.

## 8. Fallback contract

Fallback never widens authorisation, selection, MIME, limits, sensitivity,
locality, or required capability.

Use this precedence:

1. same deterministic chain with a narrower bounded selection;
2. an approved equivalent deterministic processor/profile;
3. existing adequate normalised or structured evidence;
4. an approved alternate specialist route with equal required capabilities and
   policy eligibility;
5. omit optional specialist evidence with an attributed omission notice;
6. `DEFER` for missing evidence/policy/availability;
7. `REJECT` for safety or authorisation failure.

Never fall back from deterministic spreadsheet calculation to model arithmetic.
Never fall back from local-only to remote. Never turn direct Office-original or
video-temporal interpretation operational. Never reinterpret provider
transport as model behaviour.

## 9. Locality and classification

P2-05 must define the shape and ownership of later policy inputs, but must not
invent decisions.

Required distinctions:

- provider processing locality;
- document sensitivity/classification;
- consent or disclosure permission;
- remote-processing eligibility;
- route-specific locality requirement;
- data minimisation decision.

`DOC_CLASS` remains content purpose. `LOCAL` provider metadata does not by
itself authorise processing. Until a separately approved mapping exists, every
binary/specialist route remains remote-ineligible and fails closed when a
locality decision is required.

## 10. Availability, health, quality, and cost

Define controlled observation records with:

- capability-requirement identity and exact candidate identity;
- observation kind and value;
- source;
- observed/checked timestamp;
- expiry;
- provenance;
- safe reason;
- no prompt/content/provider payload.

Health is observation, not capability evidence. Availability must not trigger
model loading or download. Quality requires an approved evaluation profile and
fixture set. Cost requires a controlled unit and effective period. Missing or
stale values follow explicit fail-closed or neutral policy; they are never
guessed.

## 11. Deliverables after authorisation

Produce:

- a standalone P2-05 implementation/planning record under
  `docs/pending_work`;
- eligibility and denial matrices;
- deterministic candidate-order specification;
- fallback matrix and stable reason codes;
- locality/classification decision contract;
- quality/cost/availability/health observation contract;
- mapping from every P2-04 branch to required route kinds;
- structural tests proving no MIME-to-model or transport-to-behaviour shortcut;
- regression tests preserving Phase 1 and deterministic authority;
- a master-plan update only after validation;
- a standalone P2-06 secure binary materialisation plan.

Do not add routing code, providers, processors, configuration flags, database
routing tables, health probes, APEX pages, or invocation paths unless separately
authorised as P2-05 implementation work.

## 12. Tests

Tests must prove:

- an absent concrete-model evidence row is ineligible;
- the same specialist route requirement can select either of two configured
  synthetic model identities when each independently satisfies the contract;
- changing the selected model changes the eligibility snapshot and audit
  identity without changing route authority;
- `API_DECLARED` never satisfies model behaviour;
- expired/rejected evidence is ineligible;
- adapter `NOT_IMPLEMENTED` is ineligible;
- representation and MIME are independently checked;
- every required capability is satisfied;
- bounds are dimension-qualified and cannot widen during fallback;
- safety and authorisation rejection remain final;
- remote fallback is impossible without explicit policy;
- `DOC_CLASS` is not sensitivity;
- deterministic spreadsheet calculation remains authoritative;
- optional specialist omission preserves deterministic evidence;
- ordering is stable and independent of row/install/filesystem order;
- provider failures do not load/download a model;
- Phase 1 prompt-only and `TEXT`/`LOCAL` behaviour remains unchanged.

Tests must be offline and require no network, model, provider state, inference,
managed document content, or mutable database state.

## 13. Implementation sequence after authorisation

1. Reconfirm P2-03 and P2-04 contracts.
2. Inventory route-related metadata and consumers read-only.
3. Finalise route-kind, eligibility, and reason-code vocabularies.
4. Define locality/classification policy ownership and fail-closed gaps.
5. Define quality/cost/availability/health observation shapes and expiry.
6. Define eligibility gates.
7. Define deterministic ordering and tie-breaking.
8. Define fallback chains and non-widening invariants.
9. Map every P2-04 branch and negative case.
10. Add documentation and offline structural tests.
11. Validate that no routing, processor, attachment, probe, or invocation path
    was introduced.
12. Update the master plan and produce P2-06 planning input.

## 14. Acceptance criteria

P2-05 is complete when:

1. Every accepted P2-04 branch maps to controlled route kinds.
2. Every required capability has an explicit satisfaction rule.
3. Provider transport and model behaviour remain separate.
4. Missing/expired/rejected evidence makes a candidate ineligible and fails
   closed when no candidate satisfies the route requirement.
5. Representation, MIME, selection, and bounds are all enforced.
6. Locality/classification decisions are explicit and `DOC_CLASS` is not
   sensitivity.
7. Ordering is deterministic and policy-owned.
8. Fallback cannot widen any security or processing decision.
9. Deterministic outputs retain authority.
10. Optional specialist output remains attributed.
11. Quality, cost, availability, and health are controlled dated inputs.
12. Direct Office-original and video-temporal interpretation remain deferred.
13. Phase 1 remains compatible.
14. No provider/model is invoked, loaded, downloaded, or probed.
15. Structural and documentation tests pass.
16. The final activity produces P2-06 without implementing it.

## 15. In scope

- Read-only repository and database discovery.
- Capability-aware eligibility design.
- Deterministic ordering and tie-breaking.
- Non-widening fallback.
- Locality/classification policy shape.
- Quality/cost/availability/health observation shape.
- P2-04 branch mapping.
- Planning documentation and offline tests after authorisation.

## 16. Out of scope

- Runtime routing or provider selection.
- Processor or adapter implementation.
- Binary/attachment materialisation.
- Provider invocation, model probing, loading, download, or registration.
- Sensitivity inference or remote enablement.
- Health polling or cost collection.
- APEX administration.
- Plugin routing changes.
- Managed-store mutation.
- P2-06 through P2-10 implementation.
- Unrelated dirty-tree work.

## 17. Assumptions and blockers

Assumptions:

- P2-02 capability semantics remain authoritative.
- Implemented P2-03 evidence and bounds remain authoritative.
- Approved P2-04 policy output is immutable routing input.
- Missing evidence or policy fails closed.
- Deterministic evidence remains authoritative.

Genuine blockers:

- Real specialist invocation cannot become eligible until at least one
  configured concrete model has exact positive P2-03 evidence satisfying the
  accepted capability-requirement contract. This is an enablement blocker, not
  a blocker to defining or testing the route contract with synthetic identities.
- The capability-eligibility and deterministic model-selection evidence
  contract must be accepted before runtime routing is implemented.
- No remote route can become eligible without approved sensitivity, consent,
  and locality policy.
- Quality cannot rank routes without approved evaluation fixtures/profiles.
- Availability/health checks must not load or download models.
- P2-06 cannot materialise binary attachments until P2-05 produces an approved
  selected route and exact bound contract.

## 18. Final activity

Return to:

`@orac_document_materialisation_enhancements_plan`

`thread://019ff810-7695-7282-84e4-5fce86936a56`

Produce a standalone, copy/paste-ready P2-06 plan defining secure binary
materialisation from an approved P2-05 route. Do not implement P2-06 during that
planning activity.
