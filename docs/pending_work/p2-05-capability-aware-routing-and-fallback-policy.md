# P2-05 Capability-Aware Routing and Fallback Policy

Status: completed policy and implementation-planning record; no routing runtime
is implemented by this document.

Evidence date: 2026-08-23.

Source plan:
[`orac_document_materialisation_enhancements_plan.md`](orac_document_materialisation_enhancements_plan.md).

Execution plan:
[`p2-05-capability-aware-routing-and-fallback-plan.md`](p2-05-capability-aware-routing-and-fallback-plan.md).

Primary inputs:

- [P2-04 media-type processing policy](p2-04-media-type-processing-policy.md)
- [P2-03 controlled model/provider metadata](p2-03-controlled-model-provider-metadata.md)
- [P2-02 controlled capability taxonomy](p2-02-controlled-capability-taxonomy.md)
- [P2-01 binary/multimodal use cases](p2-01-binary-multimodal-use-case-catalogue.md)

## 1. High-confidence findings

- The least-privileged `orac-service` saved connection was unavailable. A
  bounded read-only inspection used the context-mapped `orac-db` fallback.
- All nine P2-03 Core tables and six Code projections inspected are `VALID`.
  The deployed seed contains two providers, 23 capabilities, 13
  representations, three MIME values, and six provider-input declarations.
- Provider-input declarations comprise implemented text transport for Ollama
  and LM Studio plus image transport whose adapter status is
  `NOT_IMPLEMENTED`. All six declarations are current and `API_DECLARED`.
- There are no provider or model input limits, no concrete-model capability
  evidence, no model-input associations, and no current or expired positive
  model evidence.
- The 20 enabled registry rows have no provider referential orphans. There are
  no duplicate provider inputs, duplicate current model evidence records, or
  direct MIME-to-model columns.
- The only deployed routing-relevant locality field is provider processing
  locality. No LLM metadata field supplies sensitivity, remote eligibility,
  quality, cost, availability, or health policy.
- None of the six P2-03 Code routing projections has an outgoing object grant.
  No current runtime, APEX, or plugin consumer uses them as routing authority.
- `ProviderRegistry.validate_or_prepare_model()` can list and pull a missing
  Ollama model. Routing evaluation, observation, and fallback must never call
  that preparation path. LM Studio validation lists loaded models but does not
  load one.
- Current connectors pin one configured provider, service URL, and model. The
  existing evidence-submission guard forbids endpoint fallback and bounds
  pre-output retries.
- Phase 1 materialisation and model evidence remain disabled by default,
  prompt-string-only, normalised-text-only, and `TEXT`/`LOCAL` guarded.
- Plugin matching and arbitration select plugin action candidates under a
  separate host-owned policy. Plugin ranking, install order, and plugin-owned
  capability declarations are not model or processor routing evidence.

No document content, prompt, filename, source path, managed key, credential,
provider payload, model reply, provider model list, or managed-store byte was
inspected.

## 2. Current operational conclusion

There is no eligible new specialist route and no reviewed P2-05 deterministic
processor route. All binary/specialist branches remain `DEFER` until their
P2-04 prerequisites and P2-05 evidence/policy gates are satisfied.

The existing Phase 1 primary text path is a compatibility surface, not a new
P2-05 candidate. P2-05 does not infer `text_reasoning` evidence from `TEXT`,
enabled registry state, configured provider, or successful legacy invocation.

The absence of an eligible concrete model prevents a real specialist
selection; it does not make one model part of route authority. Specialist route
authority is the immutable requirement contract derived from P2-04. Exact
concrete-model evidence is candidate eligibility input, and the selected
candidate becomes an immutable per-evaluation selection snapshot.

## 3. Policy authority and precedence

P2-05 consumes one immutable P2-04 result. It never changes the P2-04
disposition, deterministic chain, required capabilities, representation,
selection, bounds, safety decision, or fallback authority.

Precedence is:

1. P2-04 authorisation and safety disposition;
2. immutable policy identity, version, selection, and bounds;
3. route-kind capability satisfaction;
4. processor evidence or specialist capability-requirement completeness;
5. transport, adapter, representation, and MIME compatibility;
6. candidate concrete-model evidence, effective dates, and
   dimension-qualified limits;
7. explicit sensitivity, consent, locality, and minimisation decisions;
8. current availability/health and approved quality/cost policy;
9. deterministic ordering;
10. non-widening fallback.

An earlier rejection or deferral cannot be overridden by ranking, health,
cost, transport, fallback, or administrator priority.

## 4. Controlled route kinds

| Route kind | Identity | Authority | Current state |
| --- | --- | --- | --- |
| `DETERMINISTIC_PROCESSOR` | Processor code, reviewed profile and immutable version | P2-04 deterministic chain | No reviewed P2-05 processor route exists |
| `SPECIALIST_MODEL` | Versioned capability-requirement identity and fingerprint | P2-04 optional attributed interpretation requirements; no concrete model is route authority | Requirement can be defined and tested; real selection is unavailable because no configured candidate has positive evidence |
| `NORMALISED_EVIDENCE_FALLBACK` | Verified artefact/output-set identity | Existing deterministic source or derivative evidence | Eligible only when P2-04 declares it adequate |
| `PRIMARY_TEXT_COMPATIBILITY` | Existing configured primary-text route | Existing Phase 1 guards only | Preserved; not selected or broadened by P2-05 |

`PRIMARY_TEXT_COMPATIBILITY` does not satisfy a binary or specialist
capability. A plugin identity, plugin candidate, provider transport row, MIME
row, registry row order, or filesystem entry is never a route-kind identity.

## 5. Routing input contract

Required immutable inputs are:

- P2-04 policy result identity, policy version, disposition, and reason;
- authorisation/source-identity snapshot and evaluation timestamp;
- required and optional capability codes;
- intended route kind;
- required representations and independent optional MIME constraints;
- bounded selection coordinates and dimension-qualified limits;
- deterministic processor/profile/version identity when applicable;
- specialist capability-requirement identity, version, fingerprint, required
  evidence maturity, and selection-policy identity when applicable;
- bounded configured-candidate set with exact model capability evidence,
  model-input associations, provider-input transport associations, and
  adapter-support state when evaluating a real specialist selection;
- all relevant effective-from/effective-to timestamps;
- explicit sensitivity, consent, locality, remote-eligibility, and data-
  minimisation decision references when applicable;
- approved current quality, cost, availability, and health observation
  identities when required by policy;
- route-policy version, fallback-chain identity, and evaluation timestamp.

The evaluator must not accept a path, managed key, credential, arbitrary URL,
provider-native payload, prompt, document content, filename, or unbounded
selection.

## 6. Routing output contract

The immutable result contains only:

- disposition: `SELECTED`, `FALLBACK`, `DEFER`, or `REJECT`;
- safe reason code and preserved P2-04 reason where applicable;
- selected route kind and its controlled capability-requirement identity;
- deterministic processor/profile/version or the exact runtime-selected
  provider, `llm_id`, immutable revision/digest, model-evidence identity, and
  model-input/provider-input association snapshot;
- required transport and evidence association identities;
- satisfied and unresolved capability codes;
- independent representation and MIME decisions;
- bounded selection and applied dimension-qualified limits;
- fallback-chain identity and step;
- policy/evidence/selection fingerprints;
- locality/classification/consent/minimisation decision references;
- observation identities and evaluation timestamp;
- bounded safe audit fields.

The result must not contain prompts, content, filenames, paths, managed keys,
credentials, arbitrary URLs, raw provider metadata, provider payloads, or
unbounded media.

## 7. Eligibility gates and reason codes

| Order | Gate | Eligible rule | Failure disposition and reason |
| ---: | --- | --- | --- |
| 1 | P2-04 disposition | Exactly `ACCEPT` | Preserve safety/auth rejection as `REJECT`; otherwise `DEFER` / `RTE_POLICY_NOT_ACCEPTED` |
| 2 | Approval currency | Source, authorisation, policy version, selection and bounds are current | `REJECT` / `RTE_APPROVAL_INVALID` for identity/authorisation; otherwise `DEFER` / `RTE_APPROVAL_STALE` |
| 3 | Capability completeness | One route kind satisfies every required capability | `DEFER` / `RTE_REQUIRED_CAPABILITY_MISSING` |
| 4 | Deterministic review | Processor, profile and immutable version are reviewed | `DEFER` / `RTE_PROCESSOR_UNREVIEWED` |
| 5 | Specialist requirement | Capability, representation/MIME, behavioural-evidence maturity, output, limit, locality/data-handling, and fallback requirements form one complete immutable contract | `DEFER` / `RTE_REQUIREMENT_CONTRACT_INCOMPLETE` or `RTE_SELECTION_POLICY_MISSING` |
| 6 | Transport | Current `API_DECLARED` provider association exists | `DEFER` / `RTE_TRANSPORT_UNSUPPORTED` |
| 7 | Adapter | Association is `IMPLEMENTED` | `DEFER` / `RTE_ADAPTER_UNSUPPORTED` |
| 8 | Representation | Required representation association matches | `DEFER` / `RTE_REPRESENTATION_UNSUPPORTED` |
| 9 | MIME | When P2-04 requires MIME, its independent exact/family rule matches | `DEFER` / `RTE_MIME_UNSUPPORTED` |
| 10 | Model eligibility | At least one configured candidate has current `MODEL_METADATA_VERIFIED` or `BOUNDED_PROBE_VERIFIED` evidence satisfying every required capability and association | Candidate exclusion using `RTE_MODEL_EVIDENCE_ABSENT`, `RTE_MODEL_EVIDENCE_EXPIRED`, `RTE_MODEL_EVIDENCE_REJECTED`, or `RTE_MODEL_CAPABILITY_MISMATCH`; `DEFER` / `RTE_NO_ELIGIBLE_MODEL` when none remain |
| 11 | Effective time | Every selected association is effective | `DEFER` / `RTE_ASSOCIATION_EXPIRED` |
| 12 | Limits | Every mandatory dimension has a covering bound; apply the smaller of route, provider/model, and host limits | `DEFER` / `RTE_LIMIT_MISSING`; `REJECT` / `RTE_LIMIT_EXCEEDED` |
| 13 | Sensitivity/locality | Explicit decisions permit the requirement and selected provider/model candidate | `DEFER` / `RTE_LOCALITY_POLICY_MISSING` or `RTE_CLASSIFICATION_POLICY_MISSING`; `REJECT` / `RTE_LOCALITY_DENIED` or `RTE_CLASSIFICATION_DENIED` |
| 14 | Availability/health | Required candidate observations are current and policy-acceptable | `DEFER` / `RTE_OBSERVATION_MISSING`, `RTE_OBSERVATION_STALE`, or `RTE_ROUTE_UNAVAILABLE` |
| 15 | Quality/cost | Approved policy is satisfied when applicable | `DEFER` / `RTE_QUALITY_POLICY_MISSING` or `RTE_COST_POLICY_MISSING`; `REJECT` / `RTE_QUALITY_DENIED` or `RTE_COST_DENIED` |
| 16 | Deterministic selection | Policy ordering chooses one candidate and freezes its complete evidence snapshot | `DEFER` / `RTE_MODEL_SELECTION_AMBIGUOUS` |
| 17 | Audit determinism | Requirement, selected candidate/evidence, and fallback identities fingerprint deterministically | `DEFER` / `RTE_AUDIT_IDENTITY_INCOMPLETE` |

Successful outcomes use `RTE_SELECTED`, `RTE_FALLBACK_SELECTED`, or
`RTE_OPTIONAL_SPECIALIST_OMITTED`.

`API_DECLARED`, provider `LOCAL`, registry `TEXT`, MIME presence, enabled
registry state, a health observation, or provider availability is insufficient
to satisfy behavioural capability evidence.

## 8. Capability satisfaction rules

| Capability class | Satisfaction authority |
| --- | --- |
| `DETERMINISTIC_INSPECTION` | Reviewed deterministic processor/profile/version with bounded structured output |
| `DETERMINISTIC_TRANSFORMATION` | Reviewed deterministic processor/profile/version producing the P2-04 representation |
| `DETERMINISTIC_CALCULATION` | Reviewed calculation engine/profile/version; result remains authoritative |
| `SPECIALIST_INTERPRETATION` | Model-neutral route requirement; a configured candidate satisfies it only with exact current positive concrete-model evidence plus compatible model-input and provider-input associations for every required code |
| `PRIMARY_TEXT_REASONING` | Existing Phase 1 compatibility path until a later authorised migration; never inferred for a new route from `TEXT` alone |

One candidate may satisfy multiple required codes only when each association is
explicit. Optional capabilities never repair a missing required capability.

## 9. Deterministic candidate ordering

After all eligibility gates, compare the following lexicographic tuple:

1. required authoritative deterministic processor before optional specialist;
2. policy-owned locality rank;
3. evidence maturity: `BOUNDED_PROBE_VERIFIED` before
   `MODEL_METADATA_VERIFIED`;
4. approved quality tier;
5. approved cost class;
6. current availability class then health class;
7. explicit administration priority;
8. stable configured-candidate identity.

The full tuple is recorded in bounded audit metadata. Stable identity is the
final tie-break, so database row, install, registration, filesystem, discovery,
embedding, model-output, or provider-return order cannot affect selection.

## 10. Controlled observation contract

Each observation names the capability-requirement identity and, where it
describes a provider/model property, one exact configured-candidate identity.
It includes observation kind, controlled value, source, observed timestamp,
expiry, provenance, evaluation profile where applicable, safe reason, and
immutable fingerprint. Candidate observations are eligibility/ranking inputs;
they do not alter route authority.

| Observation | Controlled values | Additional required evidence |
| --- | --- | --- |
| Availability | `AVAILABLE`, `DEGRADED`, `UNAVAILABLE`, `UNASSESSED` | Passive/non-loading observation source |
| Health | `HEALTHY`, `DEGRADED`, `UNHEALTHY`, `UNASSESSED` | Non-capability operational check |
| Quality | `PREFERRED`, `QUALIFIED`, `REJECTED`, `UNASSESSED` | Approved fixture set, evaluation profile and result |
| Cost | `APPROVED`, `CONDITIONAL`, `DENIED`, `UNASSESSED` | Controlled unit, amount/class and effective period |

No current observation value is inferred. Missing or stale values follow the
route policy's explicit fail-closed or neutral rule. Observation must never
list, load, pull, download, register, or invoke a model.

## 11. Locality and classification decision contract

The later policy owner must supply separate immutable references for:

- provider processing locality;
- document sensitivity/classification decision;
- consent/disclosure decision;
- remote-processing eligibility;
- route-specific locality requirement;
- data-minimisation decision;
- decision source, reviewer, effective period, policy version and fingerprint.

`DOC_CLASS` is content purpose, not sensitivity. Provider `LOCAL` is a fact,
not permission. Missing sensitivity/consent/locality policy fails closed.
Until separately approved policy exists, binary/specialist routes are remote-
ineligible and a local-only decision cannot fall back to remote.

## 12. Non-widening fallback contract

Every fallback step must retain or narrow the original authorisation, source
identity, selection, required capabilities, representation/MIME rule,
sensitivity, locality, consent, limits, and output authority.

| Order | Fallback | Required invariant | Outcome when unavailable |
| ---: | --- | --- | --- |
| 1 | Same deterministic chain with narrower selection | Every coordinate is a subset and all dimensions remain within original bounds | Continue |
| 2 | Equivalent deterministic processor/profile | Same outputs, authority and required capabilities | Continue |
| 3 | Adequate existing normalised/structured evidence | P2-04 explicitly permits the fallback and provenance remains verified | Continue |
| 4 | Alternate specialist candidate or equivalent specialist requirement | Same requirement contract, or an explicitly ordered equivalent contract with equal required capabilities; all policy/evidence gates pass and a new immutable selection result is issued | Continue |
| 5 | Omit optional specialist evidence | Deterministic evidence remains complete and omission is attributed | `FALLBACK` / `RTE_OPTIONAL_SPECIALIST_OMITTED` |
| 6 | No eligible route | No safety or authorisation failure | `DEFER` / `RTE_FALLBACK_UNAVAILABLE` |
| 7 | Safety or authorisation failure | Preserve the earlier failure | `REJECT` with original reason |

Fallback never substitutes model arithmetic for deterministic spreadsheet
calculation, local-only with remote, transport for behaviour, or a direct
Office/video interpretation for a deferred branch.

## 13. P2-04 branch mapping

| P2-04 family | P2-01 use case | Required route kinds | Optional route kind | Current result |
| --- | --- | --- | --- | --- |
| Markdown/CSV/JSON/plain text | Existing Phase 1 | `NORMALISED_EVIDENCE_FALLBACK`, then existing `PRIMARY_TEXT_COMPATIBILITY` | None | Existing Phase 1 path unchanged; no new P2-05 selection |
| PDF | `UC-PDF-SCAN`, `UC-PDF-VISUAL` | `DETERMINISTIC_PROCESSOR` for inspection, selection and layout/OCR/render | `SPECIALIST_MODEL` for attributed document/chart interpretation | `DEFER`: no reviewed processor/model evidence |
| Technical image | `UC-IMAGE-TECHNICAL` | `DETERMINISTIC_PROCESSOR` for inspection/selection/OCR | `SPECIALIST_MODEL` for technical-image interpretation | `DEFER` |
| Workbook | `UC-SPREADSHEET-VISUAL` | `DETERMINISTIC_PROCESSOR` for inspection, extraction, calculation and render | `SPECIALIST_MODEL` for chart interpretation | `DEFER`; deterministic calculation remains authoritative |
| Presentation | `UC-PRESENTATION-VISUAL` | `DETERMINISTIC_PROCESSOR` for inspection, extraction and render | `SPECIALIST_MODEL` for presentation/chart interpretation | `DEFER` |
| Audio | `UC-AUDIO-SPEECH` | `DETERMINISTIC_PROCESSOR` for metadata/selection; controlled transcription route when evidenced | `SPECIALIST_MODEL` for diarisation/interpretation | `DEFER` |
| Video | `UC-VIDEO-TEMPORAL` | `DETERMINISTIC_PROCESSOR` for metadata, selection, subtitles/keyframes | `SPECIALIST_MODEL` only after later approval | Temporal interpretation remains `DEFERRED` |
| Office original | `UC-OFFICE-ORIGINAL` | Format-specific `DETERMINISTIC_PROCESSOR` only | None | Direct original interpretation remains `DEFERRED` |

Unsafe containers, MIME-provider shortcuts, model arithmetic, caller
paths/keys, policy-free remote processing, unbounded media, and direct deferred
interpretations remain final negative cases.

## 14. Provider failure and side-effect boundary

Candidate construction and observation read only controlled metadata. They
must not construct a connector or call provider discovery/preparation methods.
In particular, they must not call `validate_or_prepare_model()`, `list_models()`,
Ollama `list`/`pull`, LM Studio `/v1/models`, or any inference endpoint.

A provider failure after a future authorised selection may only move through
the approved fallback chain. It cannot cause model loading/download, endpoint
substitution, bound growth, wider selection, or evidence fabrication.
P2-07 cannot choose another model inside an invocation. Any alternate candidate
must be selected by a fresh P2-05 evaluation and carried by a new result and,
where bytes will be consumed, a newly authorised P2-06 attachment.

## 15. Implementation boundary

This activity adds policy/planning documentation and offline structural tests
only. It does not add routing code, route tables, provider/model rows,
processor profiles, quality/cost/health observations, configuration flags,
APEX pages, attachments, probes, adapters, connectors, plugin behaviour,
managed-store changes, or invocation paths.

The P2-03 Code views remain unconsumed routing metadata. Phase 1 behaviour and
its disabled feature defaults remain unchanged.

## 16. Acceptance evidence

Offline tests must prove:

- all P2-04 families and P2-01 use cases map to controlled route kinds;
- missing, expired, or rejected model evidence is ineligible;
- route authority is unchanged when two synthetic eligible model identities
  are substituted under the same capability-requirement fingerprint;
- deterministic ordering freezes exactly one selected provider/model/evidence
  snapshot and ambiguous selection fails closed;
- `API_DECLARED` and `TEXT` cannot establish model behaviour;
- adapter `NOT_IMPLEMENTED` is ineligible;
- representation and MIME remain independent;
- required capabilities and dimension-qualified limits are complete;
- safety/authorisation failure is final and fallback cannot widen;
- `DOC_CLASS` is not sensitivity and local-only cannot become remote;
- spreadsheet calculation remains deterministic authority;
- optional specialist omission remains attributed;
- ordering is deterministic and independent of incidental order;
- routing/observation cannot load or download a model;
- Office-original and video-temporal interpretation remain deferred;
- existing Phase 1 prompt-only behaviour remains unchanged.

The standalone next-stage planning input is
[`p2-06-secure-binary-materialisation-plan.md`](p2-06-secure-binary-materialisation-plan.md).
