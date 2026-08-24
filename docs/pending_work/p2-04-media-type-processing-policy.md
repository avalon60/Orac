# P2-04 Media-Type Processing Policy

Status: completed policy and implementation-planning record; no processing
runtime is implemented by this document.

Evidence date: 2026-08-23.

Source plan:
[`orac_document_materialisation_enhancements_plan.md`](orac_document_materialisation_enhancements_plan.md).

Primary inputs:

- [P2-03 controlled model/provider metadata](p2-03-controlled-model-provider-metadata.md)
- [P2-02 controlled capability taxonomy](p2-02-controlled-capability-taxonomy.md)
- [P2-01 binary/multimodal use cases](p2-01-binary-multimodal-use-case-catalogue.md)

## 1. High-confidence findings

- P2-03 is deployed: two reviewed providers, 23 capabilities, 13
  representations, three exact image MIME values, six provider transport
  declarations, and no concrete-model capability evidence.
- Current stored sources are 59 Markdown and one DOCX. All 60 ingestion
  requests completed to `text/markdown; charset=utf-8` `PRIMARY`
  artefacts.
- Stored source MIME has no null, uppercase, parameterised, or malformed value.
  Current sources are `text/markdown` and the standard DOCX MIME value.
- No deterministic detected-MIME, encrypted, active-content, corruption, or
  expansion-risk characteristic is stored for the 60 current extractions or
  artefacts.
- No deployed Core/API/Code source maps MIME directly to `llm_id`.
- Drop Box trusts an allowlisted extension only long enough to select a recipe,
  then validates UTF-8, archive structure, or RTF/HTML signatures before
  conversion. It does not implement PDF, image, workbook, presentation, audio,
  or video processing.
- Phase 1 remains bounded normalised text only. Raw binary and page selection
  remain rejected, and spreadsheet calculations are not delegated to a model.

## 2. Tentative inferences

- Existing source MIME is declared/recipe metadata, not a general
  signature-derived media detector.
- The current extraction JSON shapes do not provide a safe generic location for
  P2-04 characteristics. Future inspectors should return controlled structured
  evidence rather than add ad-hoc flags to existing metadata.
- Because no P2-01 use case has an approved fixture and no model has positive
  P2-03 evidence, every specialist branch remains descriptive and
  non-operational.

## 3. Main entry points

- `src/orac_core/knowledge/materialisation_policy.py` owns current Phase 1
  normalised materialisation decisions.
- `src/orac_core/knowledge/materialisation.py` validates and emits authorised
  normalised parts.
- `src/orac_core/knowledge/model_submission.py` owns current flat-text
  submission guards.
- `plugins/drop_box/conversion.py` owns current Drop Box format recipes and
  deterministic signature/container validation.
- P2-03 Code views expose safe provider/capability/representation/MIME/evidence
  metadata without making it operational.

## 4. Key modules and responsibilities

| Area | Current responsibility | P2-04 boundary |
| --- | --- | --- |
| Managed store/retrieval | Authorised immutable identity and verified bytes | Remains the only source-byte authority |
| Deterministic inspector | Not yet generalised | Must establish representation and characteristics |
| Materialisation policy | Normalised text levels | Remains unchanged until later runtime authorisation |
| Drop Box | Allowlisted Phase 1 conversion | Does not become the P2-04 binary processor |
| P2-03 metadata | Controlled catalogues and evidence | Supplies vocabulary, never routing authority |
| Model adapters | Prompt strings | Receive no attachment or binary API |
| Specialist processor | Not implemented | May only consume a future bounded selection |

## 5. Important control and data flows

The future policy flow is:

1. validate authorisation and immutable source identity;
2. reconcile declared MIME with signature/container inspection;
3. apply safety rejection or deferral;
4. apply deterministic content-characteristic overrides;
5. validate the explicit bounded user outcome and selection;
6. apply one media-family default;
7. prefer adequate existing normalised/structured evidence;
8. describe optional specialist evidence requirements.

Policy never resolves a provider, model, endpoint, health state, price, or
remote-processing decision.

An optional specialist branch is therefore a model-neutral capability
requirement contract, not a concrete-model route. It states the required
capabilities, representations, independent MIME constraints, bounded
selection, output contract, evidence maturity, and dimension-qualified limits.
P2-05 owns matching configured concrete models against that contract and
freezing the selected eligibility evidence for one evaluation.

## 6. Fragile or high-risk areas

- Extension or declared MIME can currently select a Drop Box recipe; it must not
  become binary routing authority.
- Existing JSON has no governed cross-format characteristic schema.
- `DOC_CLASS` describes content purpose, not sensitivity.
- Provider image transport is `API_DECLARED` while adapter support is
  `NOT_IMPLEMENTED`; transport must not become behavioural eligibility.
- Whole-container expansion, Office active content, formula caches, hidden
  workbook/slide objects, and media duration/frame counts need deterministic
  evidence before a branch can be accepted.
- Existing Phase 1 broad-text guards are compatibility surfaces and must not be
  weakened by a binary policy implementation.

## 7. Open evidence questions

- Approved representative fixtures and owners remain absent.
- No measured expansion/output envelopes exist for the proposed processors.
- No deterministic inspector contract has been selected for each binary family.
- No configured model/revision currently has positive P2-03 behavioural
  evidence, so no real specialist invocation can become eligible. This does
  not make a concrete model part of P2-04 authority or block model-neutral
  policy, routing-contract, adapter-contract, or audit-contract planning.
- Sensitivity, consent, locality, remote eligibility, cost, quality, and health
  policy remain unresolved and belong to P2-05 or later.

These gaps fail closed; they do not block completion of this planning record.

## 8. Policy input and output contract

Independent inputs are:

- immutable authorised source identity;
- declared MIME;
- verified detected representation;
- exact or family MIME match;
- signature/container status;
- deterministic characteristics;
- requested user outcome;
- available source and derivative representations;
- deterministic and optional specialist capability requirements;
- bounded selection coordinates;
- dimension-qualified bounds;
- policy version.

The output contains only:

- disposition: `ACCEPT`, `DEFER`, or `REJECT`;
- safe reason code;
- required inspection capability;
- ordered deterministic transformation/calculation steps;
- required output representations;
- optional specialist capabilities;
- a deterministic specialist-requirement fingerprint compiled only from the
  capability, representation/MIME, selection, output, evidence-maturity, and
  limit requirements;
- bounded selection contract;
- applicable dimension-qualified limits;
- normalised/structured fallback representation;
- unresolved evidence or policy requirements.

The output must not contain a provider code, `llm_id`, service endpoint, cost
order, health state, or remote-eligibility decision.

## 9. Decision precedence

| Order | Decision | Rule |
| ---: | --- | --- |
| 1 | Authorisation and source identity | Missing or changed identity rejects |
| 2 | Signature/container reconciliation | Verified characteristics outrank declaration |
| 3 | Safety | Corrupt, encrypted, active, unsupported nesting, expansion-risk, or unbounded input rejects/defers |
| 4 | Characteristic override | Deterministically evidenced characteristics supersede MIME default |
| 5 | User outcome and selection | Must be explicit, authorised, and bounded |
| 6 | Media-family default | Exactly one controlled default |
| 7 | Adequate fallback | Prefer existing normalised/structured evidence |
| 8 | Specialist requirement | Optional attributed evidence only |

An earlier rejection cannot be overridden by a later default.

## 10. Media-family default matrix

| Family | Default deterministic chain | Characteristic override | Required representations | Specialist point | Default fallback |
| --- | --- | --- | --- | --- | --- |
| Markdown/CSV/JSON/plain text | Existing Phase 1 verification and normalisation | None introduces binary processing | `normalised_text_evidence` | `text_reasoning` under existing Phase 1 guards | Existing bounded text |
| PDF | `container_inspection → bounded_media_selection → layout_extraction` | Scanned/unreliable text adds page render and OCR; layout outcome adds bounded render | `verified_source_container`, `inspection_metadata`, `structured_derivative`; optional `raster_image_derivative` | Document/chart interpretation after deterministic evidence | Extracted text/layout evidence |
| Technical image | `container_inspection → bounded_media_selection`; coordinate-aware OCR when text matters | Spatial/topology/colour/icon outcome requests optional specialist evidence | `verified_source_media`, `inspection_metadata`, optional `structured_derivative` | Technical-image interpretation | OCR/inspection metadata or manual description |
| Workbook | `container_inspection → workbook_structured_extraction` | Formula outcome adds deterministic calculation; chart/layout outcome adds bounded render | `verified_source_container`, `structured_derivative`, optional `sheet_chart_render` | Chart interpretation consumes render plus authoritative cells/series | Structured cells/formulas/calculation |
| Presentation | `container_inspection → presentation_structured_extraction` | Composition/diagram/chart outcome adds bounded slide render | `verified_source_container`, `structured_derivative`, optional `slide_render` | Presentation/chart interpretation | Structured slide/object/notes evidence |
| Audio | `audio_metadata_inspection → bounded_media_selection` | Speech adds transcription; material speaker changes may add diarisation | `verified_source_media`, `inspection_metadata`, `decoded_audio_selection`; optional `time_aligned_text` | Speech/diarisation/audio interpretation | Authoritative transcript where present; otherwise metadata |
| Video | `video_metadata_inspection → bounded_media_selection → subtitle_extraction` when authoritative subtitles exist | Optional bounded deterministic keyframes | `verified_source_media`, `inspection_metadata`, `bounded_selection_manifest`; optional `video_frame_selection` | Temporal interpretation remains deferred | Subtitles, metadata, and selected frames |
| Office original | Format-specific deterministic inspection, extraction, calculation, and rendering only | Active/encrypted/external-link conditions fail closed | Container plus format-specific derivatives | Direct original interpretation deferred | Normalised or structured derivative |

For workbook outcomes, deterministic calculation remains authoritative. A
specialist result is a separate attributed evidence item and cannot overwrite
authoritative cells, formulae, chart-series data, or deterministic results.

## 11. Characteristic override matrix

| Characteristic | Evidence authority | Disposition | Reason code | Required outcome |
| --- | --- | --- | --- | --- |
| Source identity unauthorised/changed | Managed-store verification | `REJECT` | `MED_SOURCE_IDENTITY_INVALID` | No processing |
| Signature mismatch | Deterministic signature inspection | `REJECT` | `MED_SIGNATURE_MISMATCH` | No declared-MIME fallback |
| Ambiguous/unsupported representation | Deterministic inspection | `DEFER` | `MED_REPRESENTATION_UNSUPPORTED` | Approved inspector/profile required |
| Corrupt structure | Deterministic inspection | `REJECT` | `MED_CORRUPT_STRUCTURE` | Safe diagnostic only |
| Encrypted content | Deterministic inspection | `DEFER` | `MED_ENCRYPTED_CONTENT` | Separately authorised decryption path |
| Active content/macros | Deterministic inspection | `REJECT` | `MED_ACTIVE_CONTENT` | Never execute |
| External references | Deterministic inspection | `DEFER` | `MED_EXTERNAL_REFERENCE` | No acquisition; approved snapshot required |
| Nested/expanded bounds exceeded | Deterministic inspection | `REJECT` | `MED_EXPANSION_LIMIT` | No partial hidden expansion |
| Required bound unavailable | Inspection/selection evidence | `DEFER` | `MED_BOUND_UNKNOWN` | Dimension-qualified bound required |
| Embedded text missing/unreliable | Layout/text inspection | `ACCEPT` override | `MED_OCR_REQUIRED` | Bounded render plus OCR |
| Scanned content | Layout/text inspection | `ACCEPT` override | `MED_SCANNED_CONTENT` | Bounded render plus OCR |
| Formula present and outcome depends on result | Workbook inspection | `ACCEPT` override | `MED_CALCULATION_REQUIRED` | Deterministic calculation |
| Formula cache stale/absent | Workbook inspection | `DEFER` | `MED_FORMULA_CACHE_UNRELIABLE` | Approved calculation engine |
| Chart/layout dependence | Structured inspection plus user outcome | `ACCEPT` override | `MED_RENDER_REQUIRED` | Bounded render plus structured evidence |
| Hidden sheets/slides/objects | Deterministic inspection | `DEFER` | `MED_HIDDEN_CONTENT` | Explicit selection/policy |
| Authoritative transcript/subtitle exists | Registered provenance | `ACCEPT` override | `MED_AUTHORITATIVE_TEXT_AVAILABLE` | Prefer text; avoid redundant transcription |
| Speech required without transcript | Audio inspection | `DEFER` until processor exists | `MED_TRANSCRIPTION_REQUIRED` | Bounded decoded selection |
| Whole/unbounded audio/video | Selection evidence | `REJECT` | `MED_UNBOUNDED_MEDIA` | Explicit time/track/frame selection |
| Adequate normalised evidence | Existing verified artefact | `ACCEPT` fallback | `MED_NORMALISED_SUFFICIENT` | Avoid binary/specialist path |

## 12. Deterministic processing-chain catalogue

| Chain | Ordered capabilities | Output |
| --- | --- | --- |
| `CHAIN_TEXT_EXISTING` | Existing Phase 1 verification | `normalised_text_evidence` |
| `CHAIN_CONTAINER_INSPECT` | `container_inspection` | `inspection_metadata` |
| `CHAIN_PDF_LAYOUT` | Container inspect, selection, `layout_extraction` | `structured_derivative` |
| `CHAIN_PDF_OCR` | Container inspect, selection, `page_rendering`, `ocr_text_extraction` | Raster plus structured OCR |
| `CHAIN_IMAGE_OCR` | Media inspect, selection, `ocr_text_extraction` | Coordinate-aware structured OCR |
| `CHAIN_WORKBOOK_STRUCTURED` | Container inspect, `workbook_structured_extraction` | Structured workbook derivative |
| `CHAIN_WORKBOOK_CALCULATE` | Workbook structured, `spreadsheet_calculation` | Authoritative calculated derivative |
| `CHAIN_WORKBOOK_RENDER` | Workbook structured, selection, `sheet_chart_rendering` | `sheet_chart_render` |
| `CHAIN_PRESENTATION_STRUCTURED` | Container inspect, `presentation_structured_extraction` | Structured presentation derivative |
| `CHAIN_PRESENTATION_RENDER` | Presentation structured, selection, `slide_rendering` | `slide_render` |
| `CHAIN_AUDIO_SELECT` | `audio_metadata_inspection`, selection | `decoded_audio_selection` |
| `CHAIN_AUDIO_TRANSCRIBE` | Audio select, `speech_transcription` | `time_aligned_text` |
| `CHAIN_VIDEO_EVIDENCE` | `video_metadata_inspection`, selection, optional subtitle/keyframe extraction | Metadata, text, selected frames |

A specialist result is a separate attributed evidence item and cannot overwrite
a deterministic output.

## 13. Bounds by family

Every accepted/deferred branch names relevant P2-03 dimensions:

| Family | Mandatory dimensions |
| --- | --- |
| All | `BYTES`, `OUTPUT_BYTES`, `RETRIES`, `ELAPSED_TIME` |
| Containers | `MEMBERS`, `EXPANDED_BYTES`, `OBJECTS` |
| PDF/presentation | `PAGES` or `OBJECTS`, `PIXELS` when rendered |
| Workbooks | `MEMBERS`, `OBJECTS`, `CELLS`, `PIXELS` when rendered |
| Images | `PIXELS` |
| Audio | `DURATION`, `CHANNELS` |
| Video | `DURATION`, `CHANNELS`, `FRAMES`, `PIXELS` |
| Specialist/text stages | `INPUT_TOKENS`, `OUTPUT_TOKENS`, `OUTPUT_BYTES`, `RETRIES`, `ELAPSED_TIME` |

There is no universal maximum and no JSON limit set.

## 14. P2-01 mapping

| Use case | Policy branch | Current result |
| --- | --- | --- |
| `UC-PDF-SCAN` | PDF scanned override → `CHAIN_PDF_OCR` | `DEFER`: inspector/fixture absent |
| `UC-PDF-VISUAL` | PDF layout/render branch | `DEFER`: inspector/fixture absent |
| `UC-IMAGE-TECHNICAL` | Technical image inspect/OCR plus optional specialist | `DEFER`: inspector and eligible-model evidence absent |
| `UC-SPREADSHEET-VISUAL` | Workbook structured/calculate/render | `DEFER`: processor/fixture absent |
| `UC-PRESENTATION-VISUAL` | Presentation structured/render | `DEFER`: processor/fixture absent |
| `UC-AUDIO-SPEECH` | Audio inspect/select/transcribe | `DEFER`: knowledge transcription processor absent |
| `UC-VIDEO-TEMPORAL` | Video evidence chain | Temporal interpretation remains `DEFERRED` |
| `UC-OFFICE-ORIGINAL` | Format-specific deterministic derivatives | Direct original interpretation remains `DEFERRED` |

Negative cases reject adequate normalised substitutes, MIME/provider acceptance
as capability, model arithmetic, unsafe containers, caller paths/keys,
policy-free remote processing, and unbounded media.

## 15. Implementation boundary

A future P2-04 runtime implementation may add a versioned policy representation
and deterministic structural validators only after separate authorisation. It
must not add processors, adapters, attachments, provider/model routing,
sensitivity inference, remote eligibility, APEX administration, or invocation.

This planning activity changes no processor, adapter, connector signature,
managed-store content, plugin behaviour, configuration, provider/model row,
model evidence row, or service.

## 16. Acceptance evidence

Offline tests must prove:

- every family has one default;
- all P2-01 use cases map to a branch;
- safety precedence and fail-closed reason codes are complete;
- MIME and representation remain independent;
- no policy output field names a provider, model, endpoint, health, cost, or
  remote decision;
- deterministic spreadsheet calculation remains authoritative;
- specialist output is optional and attributed;
- Office-original and video-temporal interpretation remain deferred;
- Phase 1 Markdown/CSV/JSON/plain-text behaviour remains unchanged.

The standalone P2-05 planning input is
[p2-05-capability-aware-routing-and-fallback-plan.md](p2-05-capability-aware-routing-and-fallback-plan.md).
