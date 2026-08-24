# P2-03 Controlled Model and Provider Metadata

Status: implemented and validated on 23-Aug-2026.

Source plan:
[`orac_document_materialisation_enhancements_plan.md`](orac_document_materialisation_enhancements_plan.md).

Authorisation covered additive P2-03 metadata only. P2-04 runtime policy, P2-05
routing, processor implementation, attachment submission, provider/model
invocation, model probing, and remote eligibility remain unimplemented.

## Authority and eligibility clarification

P2-03 evidence describes whether one configured concrete model revision is
eligible to satisfy a capability requirement. It does not grant route
authority and must not be embedded in a route definition as a required or
"blessed" model. Route authority belongs to the versioned capability
requirement contract produced from P2-04 and owned by P2-05: required
capabilities, representations, independent MIME rules, behavioural-evidence
maturity, dimensions and limits, locality/data-handling constraints, and
fallback invariants.

At evaluation time, P2-05 may select any configured provider/model revision
whose current P2-03 provider-input, capability, model-input, limit, and
behavioural-evidence rows satisfy that complete requirement contract. The
selected concrete provider, `llm_id`, immutable model revision/digest, evidence
identities, and associations are then frozen in the route-evaluation result and
recorded as invocation/audit evidence. A different eligible model requires a
new deterministic evaluation result; it does not change the route definition.

Synthetic model and evidence identities may exercise the P2-05 through P2-08
contracts with a fake provider. They can never make a real invocation eligible.

## 1. High-confidence findings

- The mapped `orac-service` saved connection remains unavailable locally.
  Aggregate validation used the documented `orac-db` administrative fallback.
- The pre-deployment registry contained 20 enabled Ollama rows, 20 distinct
  models, no null providers, and no duplicate `(provider, model)` groups.
- No legacy `properties` object used a P2-03 reserved key.
- The reviewed Python provider registry implements exactly `ollama` and
  `lmstudio`. `openai` is not seeded.
- Existing `orac_api.llm_registry_v` remains a 13-column compatibility
  projection with its prior names and order.
- Phase 1 connector signatures remain prompt-string-only. The effective
  `TEXT` default and `TEXT`/`LOCAL` submission guards remain unchanged.

## 2. Physical model

| Logical concern | Physical table | Abbreviation |
| --- | --- | --- |
| Provider catalogue | `orac_core.llm_providers` | `llm_prov` |
| Capability catalogue | `orac_core.llm_capabilities` | `llm_cap` |
| Input representations | `orac_core.llm_input_representations` | `llm_inrep` |
| Input media types | `orac_core.llm_input_media_types` | `llm_mtype` |
| Provider input support | `orac_core.llm_provider_inputs` | `llm_prvin` |
| Provider input limits | `orac_core.llm_provider_input_limits` | `llm_pilim` |
| Model capabilities | `orac_core.llm_model_capabilities` | `llm_modcap` |
| Model-capability inputs | `orac_core.llm_model_cap_inputs` | `llm_mcin` |
| Model-input limits | `orac_core.llm_model_input_limits` | `llm_milim` |

The abbreviations are registered in
[`table-abbreviations.csv`](../agent-guardrails/table-abbreviations.csv).

## 3. Controlled domains

The protected central reference catalogue now contains:

- `CAPABILITY_CLASS`;
- `CAPABILITY_EVIDENCE_STATE`;
- `CAPABILITY_LIFECYCLE`;
- `PROVIDER_METADATA_STATUS`;
- `PROCESSING_LOCALITY`;
- `ADAPTER_SUPPORT_STATUS`;
- `MIME_MATCH_KIND`;
- `LIMIT_DIMENSION`;
- `LIMIT_UNIT`;
- `BOUND_OPERATOR`.

Each domain has a semantic Code view and an active-value LOV view. No runtime,
APEX, or plugin grant was added for those views.

The active `PROCESSING_LOCALITY` values are exactly `LOCAL`, `REMOTE`,
`HYBRID`, and `UNKNOWN`. An append-only corrective changeset deactivates the
non-contract `UNMAPPED` reference row while preserving protected-reference
history.

## 4. Seed state

The deployed seed is deliberately conservative:

| Catalogue | Count | Content |
| --- | ---: | --- |
| Providers | 2 | `ollama`, `lmstudio` |
| Capabilities | 23 | Exact P2-02 codes |
| Representations | 13 | Exact approved P2-03 representation codes |
| MIME values | 3 | `image/jpeg`, `image/png`, `image/webp` |
| Provider inputs | 6 | Two text declarations, one MIME-neutral Ollama image declaration, and three exact LM Studio image declarations |
| Model capability evidence | 0 | Absence means `UNASSESSED` |
| Model-capability inputs | 0 | No inference from `TEXT` |
| Provider limits | 0 | Await reviewed values |
| Model-input limits | 0 | Await positive model evidence |

All provider input rows are `API_DECLARED`. Text is
`IMPLEMENTED` for both reviewed adapters. Image transport is
`NOT_IMPLEMENTED`. No row claims concrete-model behaviour.

## 5. Evidence and transition enforcement

Provider transport accepts only `API_DECLARED` or `REJECTED`.
Concrete-model evidence accepts only:

- `MODEL_METADATA_VERIFIED`;
- `BOUNDED_PROBE_VERIFIED`;
- `REJECTED`.

Concrete evidence requires the exact `llm_id`, provider, model identity,
immutable revision/digest, source, checked date, effective period, reviewer, and
provenance. A trigger verifies provider/model equality with the registry row.

Bounded-probe evidence additionally requires fixture, probe, and acceptance
criteria identities. Positive evidence forbids a rejection reason; rejected
evidence requires one. Bounded-probe maturity cannot silently downgrade.
Replacing rejected evidence requires a later checked date and a new evidence
source. Rejecting evidence closes current child input associations in the same
transaction. Input associations require a current positive parent.

Expired evidence is excluded by
`orac_code.llm_current_model_evidence_v`.

## 6. MIME, representation, limits, and JSON

Representation and MIME use independent foreign keys. MIME is never linked
straight to `llm_id`. Exact values are canonical lowercase media types;
wildcards are limited to a top-level `type/*` pattern.

Provider and model-input limits use independent child tables with one
controlled dimension, operator, numeric value, unit, and effective period per
row. There is no general `max_value` JSON object.

New native JSON is:

- object-only;
- limited to 8 KiB after UTF-8 serialisation;
- restricted to the documented top-level keys `schema_version`,
  `request_fields`, `encoding_shape`, `sdk_options`, `native_labels`,
  `response_metadata`, `runtime_hints`, and `adapter_quirks`;
- checked recursively for secret, prompt, content, path, managed-key,
  capability, evidence, locality, revision, MIME-policy, health, enablement,
  and limit keys.

Legacy `llm_registry.properties` remains readable but non-authoritative.
`llm_reg_ck3` prevents new controlled capability, modality, MIME, evidence,
locality, revision, or limit structures there.

## 7. Access surfaces

The API layer has one explicit pass-through view and ungranted TAPI per new
table. Code has safe read projections for provider/capability catalogues,
provider transport, current model evidence, positive model input support, and
dimension-qualified limits.

Only `orac_api` has Core table DML. Only `orac_code` has read access to the
new API views. No new privilege or synonym was given to `orac`,
`orac_apx_pub`, `orac_plugin`, or a plugin-owned schema.

## 8. Deployment and rollback

The production path is:

`install.sql` or `install_orac.sql`
→ `productController.xml`
→ Core/API/Code schema controllers
→ object-type `includeAll` entries.

The explicit Core recovery runner includes every new Core object and places the
P2-03 seed migration before the foreign keys that validate existing registry
providers. Code post-install recompiles domain LOV views after their semantic
views exist and recompiles the existing registry TAPI, probe view, and usage
view after the additive registry DDL invalidates their dependency state.

Rollback removes dependent views, grants, packages, triggers, foreign keys,
constraints, indexes, and tables in reverse order. Protected reference domains
and values are deactivated instead of deleted. Redeployment deterministically
reactivates them.

## 9. Validation evidence

- Liquibase validation: passed.
- Scoped Liquibase update-SQL generation: passed.
- Scoped deployment through the existing `SYSTEM.DATABASECHANGELOG`: passed.
- New Core tables: 9 valid.
- New API views, package specs, and package bodies: 9 each, all valid.
- Safe Code metadata views: valid.
- Invalid `LLM_%` objects or compiler errors: none.
- Registry provider is not nullable; provider FK, reserved-key check, and
  `(provider, model)` uniqueness are enabled and validated.
- Offline P2-03/connector/submission regression: 40 tests plus 7 subtests
  passed.
- No model was queried, listed, loaded, downloaded, registered, probed, or
  invoked.

## 10. Remaining boundary

Positive model evidence still requires an immutable revision/digest and reviewed
source or approved bounded fixture/probe criteria. Remote eligibility,
sensitivity, processing policy, routing, attachments, health, cost, quality,
and runtime enablement remain later work. The next architectural gate is an
accepted capability-eligibility and deterministic model-selection contract;
it is not designation of one production model as route authority.
