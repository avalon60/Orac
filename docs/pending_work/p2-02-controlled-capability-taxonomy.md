# P2-02 Controlled Capability Taxonomy

Status: completed provider-neutral planning taxonomy; no runtime capability is
implemented or enabled by this document.

Evidence date: 2026-08-22.

Source plan:
[`orac_document_materialisation_enhancements_plan.md`](orac_document_materialisation_enhancements_plan.md).

Primary input:
[`p2-01-binary-multimodal-use-case-catalogue.md`](p2-01-binary-multimodal-use-case-catalogue.md).

## Purpose and Phase 1 boundary

This document defines stable behavioural terms for later Phase 2 metadata and
routing design. It is a controlled planning input to P2-03, not an operator
guide, provider allowlist, model declaration, or availability statement.

Phase 1 remains authoritative. Materialisation permits verified UTF-8 Markdown,
CSV, plain text, and JSON; raw-binary requests are rejected; model evidence is
submitted as one flat text prompt; and the selected model must have effective
type `TEXT` and locality `LOCAL`. PDF, Office, image, audio, and video payloads
cannot be materialised or attached to the current model path. P2-02 adds no
binary ingestion, converter, attachment, capability router, provider adapter,
security policy, database metadata, model, or deployed service.

## Evidence snapshot

The evidence categories below are deliberately separate.

### Repository facts

- `KnowledgeManagedStore` is the sole physical-path authority for immutable,
  hash-verified managed bytes. Callers supply authorised relational identities,
  never physical paths or managed-store keys.
- Current retrieval and materialisation accept only allowlisted UTF-8 text
  representations and preserve registered artefact and selection provenance.
- `KnowledgeModelSubmissionGuard` requires effective model type `TEXT`, local
  processing, a known positive context bound, and a text-evidence eligibility
  flag. Provider adapters accept prompt strings and expose no attachment
  parameter.
- Registered artefact roles are `PRIMARY`, `MANIFEST`, `TABLE`, and `METADATA`.
  Spreadsheet provenance fields describe deterministic derived members but do
  not implement workbook conversion or calculation.
- Drop Box supports native Markdown/plain-text normalisation and fixed Pandoc
  conversion for DOCX, HTML, ODT, RTF, and EPUB. It does not support PDF, OCR,
  spreadsheet, presentation, audio, video, or embedded-media extraction.
- The interactive voice loop is a microphone dialogue path. It is not a
  knowledge-ingestion, managed-audio, or reusable transcription capability.

### Read-only development database facts

The context-mapped `orac-service` saved connection was unavailable to host
SQLcl (`Unknown connection`). A bounded read-only query therefore used the
mapped `orac-db` administrative connection; it selected aggregates and metadata
only, not prompts, document content, filenames, paths, or managed-store keys.

- 20 of 20 registry rows were enabled; all were provider `ollama` with effective
  model type `TEXT`.
- All 20 `properties` values were JSON objects without `model_type`, so the
  effective type came from the current `TEXT` default.
- The latest registry creation timestamp was 2026-08-12 and the latest update
  timestamp was 2026-08-22 09:50:39.613521. No row was created or updated after
  the P2-01 evidence date. Because P2-01 recorded a date rather than an exact
  query timestamp, same-day ordering cannot be proved; counts and effective
  types nevertheless match the P2-01 snapshot.
- No Core table or view named for capability or modality existed. Capability-
  named columns found in plugin registry/invocation objects describe plugin
  execution and are not a model/media capability domain.
- Deployed `knowledge_artefacts` contained 60 `PRIMARY` rows, all
  `text/markdown; charset=utf-8`; no deployed binary or multimodal artefact role
  or media demand was observed.

### Provider documentation facts

Official documentation was checked on 2026-08-22. Ollama documents image input
alongside text and an `images` request field, and its model-details endpoint
documents a model-specific `capabilities` list. LM Studio documents base64 data
URL image input in its REST chat API, while its document-chat guide describes
adding extracted content or retrieved text to context. These are
`API_DECLARED` serving or transport observations only. They do not prove Orac
adapter support or the behaviour of any registered underlying model.

- [Ollama vision](https://docs.ollama.com/capabilities/vision)
- [Ollama model details](https://docs.ollama.com/api-reference/show-model-details)
- [LM Studio REST chat](https://lmstudio.ai/docs/developer/rest/chat)
- [LM Studio document chat](https://lmstudio.ai/docs/app/basics/rag)

The configured Ollama endpoint at `127.0.0.1:11434` was unavailable for a
metadata-only `GET /api/tags` probe on 2026-08-22. No model was downloaded,
loaded, invoked, or submitted any managed or representative content.

### Inferences and unresolved evidence

The APIs above may later transport selected images, but transport acceptance is
not evidence of OCR, document, chart, technical-image, presentation, audio, or
video behaviour. No exact provider/model/revision association is verified for
any capability in this taxonomy. P2-01 still has no approved representative
fixture, measured expansion envelope, or `VALIDATED` use case.

## Taxonomy principles

1. A capability code names one provider-neutral behavioural outcome.
2. A processor, provider, serving API, and concrete model may satisfy a
   capability; none is itself a capability.
3. Behaviour is separate from MIME/container acceptance, request transport,
   provider name, model identity, and implementation availability.
4. A capability definition is not an enabled feature. Operational state,
   policy eligibility, health, and evidence maturity are separate decisions.
5. Controlled non-generative processors precede specialist interpretation.
   Here, “deterministic” means versioned, parameter-bounded, reproducible
   processing with structured outputs; it does not claim perfect extraction.
6. The verified original remains authoritative for its bytes and appearance.
   A deterministic derivative is authoritative only for facts it extracts,
   renders, or calculates. Specialist output is attributed evidence.
7. Deterministic spreadsheet parsing and calculation remain authoritative.
   A model must not replace, recalculate, or silently contradict those facts.
8. Every applicable behaviour requires authorised identity, bounded selection,
   derivative/source provenance, explicit locality, and a safe fallback.
9. The primary text-response model receives structured deterministic and
   specialist evidence and remains responsible for the final response. It must
   identify uncertainty and must not silently overwrite authoritative facts.
10. Content-purpose `DOC_CLASS` values are not sensitivity classifications.
    `UNMAPPED` content remains ineligible for remote processing. Local is the
    conservative default, not an approved sensitivity mapping.

## Capability classes

- `PRIMARY_TEXT_REASONING`: produces the final bounded text response from
  authorised structured evidence; it does not become fact authority.
- `DETERMINISTIC_INSPECTION`: validates or describes a source/container without
  generative interpretation or content mutation.
- `DETERMINISTIC_TRANSFORMATION`: produces a versioned structured or rendered
  derivative using fixed inputs and parameters.
- `DETERMINISTIC_CALCULATION`: calculates values under an explicit engine,
  formula, precision, and error contract; its result remains authoritative.
- `SPECIALIST_INTERPRETATION`: produces attributed, confidence-bearing model or
  specialist evidence that never silently replaces source or deterministic
  facts.

## Capability-record contract

Every taxonomy record below has the following fields.

| Field | Contract |
| --- | --- |
| Capability code | Stable lower-case snake-case behavioural identifier with no provider name. |
| Display name | Concise human-readable label. |
| Capability class | One controlled class above. |
| Behaviour | Exact provider-neutral outcome. |
| Accepted representation | Source or derived input representation, separate from behaviour and MIME association. |
| Required characteristics | Traits that require or permit this behaviour. |
| Output evidence | Structured result available to downstream processing. |
| Authority | Source or deterministic representation that retains factual authority. |
| Selection contract | Required page, region, slide, sheet, chart, cell range, frame, or time selection. |
| Provenance contract | Source and derivative identities, coordinates, hashes, engine/profile, and version. |
| Bound dimensions | Policy-owned dimensions that must be limited before execution. Values here are not runtime settings. |
| Locality requirement | Conservative local default and future policy dependency. |
| Fallback | Narrower safe evidence or rejection when the behaviour cannot run. |
| Evidence status | Association evidence state; taxonomy existence is not evidence or enablement. |
| Related use cases | P2-01 identifiers served by the behaviour. |
| Deferred behaviour | Explicitly excluded extension or interpretation. |
| P2-03 metadata note | Stable facts or associations to represent later without implementing them here. |

## Stable capability records

### `text_reasoning` — Primary text reasoning

- **Capability code:** `text_reasoning`
- **Display name:** Primary text reasoning
- **Capability class:** `PRIMARY_TEXT_REASONING`
- **Behaviour:** Produce a bounded final text response from authorised structured evidence while identifying uncertainty and conflicts.
- **Accepted representation:** UTF-8 structured text evidence envelope containing references to deterministic and specialist results.
- **Required characteristics:** An authorised user question, selected evidence, explicit prompt/token budget, and current policy snapshot.
- **Output evidence:** Final response plus safe references to the evidence items used.
- **Authority:** Verified sources and deterministic results remain authoritative; the response is explanatory output.
- **Selection contract:** Consume only the approved evidence selection and its registered coordinates.
- **Provenance contract:** Record request/turn identity, evidence item identifiers, provider/model association identity, and policy fingerprint without prompt or content persistence.
- **Bound dimensions:** Input tokens, evidence share, output tokens, evidence items, retries, and elapsed time.
- **Locality requirement:** Current Orac use is local; future non-local use requires an approved sensitivity/locality decision.
- **Fallback:** Return deterministic evidence with an omission notice, request a narrower selection, or reject.
- **Evidence status:** `UNASSESSED` for P2-03 capability association; current Phase 1 text operation does not verify future taxonomy associations.
- **Related use cases:** All eight P2-01 use cases as the downstream response stage when their evidence path is eligible.
- **Deferred behaviour:** Autonomous authority, unbounded context, direct binary acceptance, and silent replacement of specialist or deterministic facts.
- **P2-03 metadata note:** Catalogue code/class relationally; associate exact models, evidence state/date/source, context bounds, and locality separately.

### `container_inspection` — Container inspection

- **Capability code:** `container_inspection`
- **Display name:** Container inspection
- **Capability class:** `DETERMINISTIC_INSPECTION`
- **Behaviour:** Verify signature, declared representation, structural integrity, member inventory, encryption, active content, and expansion risk before processing.
- **Accepted representation:** Verified managed original or registered derived container bytes resolved by authorised identity.
- **Required characteristics:** Containerised or encoded content whose safety and actual representation must be established.
- **Output evidence:** Inspection result, detected representation, member counts/types, active/encrypted flags, expansion measures, and reason codes.
- **Authority:** Verified source bytes remain authoritative.
- **Selection contract:** Inspect the whole outer container and bounded nested-member metadata; do not interpret member content.
- **Provenance contract:** Document/version identity, source hash/size, inspector/version/profile, signature result, and member coordinates.
- **Bound dimensions:** Source bytes, nested depth, members, expanded bytes, compression ratio, objects, and elapsed time.
- **Locality requirement:** Local only until sensitivity and processing policy are approved.
- **Fallback:** Reject unknown, corrupt, encrypted, active, unsupported, or excessive content.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PDF-SCAN`, `UC-PDF-VISUAL`, `UC-IMAGE-TECHNICAL`, `UC-SPREADSHEET-VISUAL`, `UC-PRESENTATION-VISUAL`, `UC-OFFICE-ORIGINAL`.
- **Deferred behaviour:** Macro execution, decryption, external-link acquisition, embedded executable processing, and content interpretation.
- **P2-03 metadata note:** Keep the capability relational; represent accepted container/MIME associations and inspector limits separately.

### `bounded_media_selection` — Bounded media selection

- **Capability code:** `bounded_media_selection`
- **Display name:** Bounded media selection
- **Capability class:** `DETERMINISTIC_INSPECTION`
- **Behaviour:** Resolve an authorised, policy-bounded subset of inspected media for a downstream processor.
- **Accepted representation:** Registered inspection metadata, structural manifests, and derivative descriptors.
- **Required characteristics:** Content larger or richer than the minimum material selection needed for the stated outcome.
- **Output evidence:** Canonical selection manifest with ordered source/derivative coordinates and aggregate measures.
- **Authority:** Registered source/derivative descriptors and authorisation decision remain authoritative.
- **Selection contract:** Page, region, image member, slide, object, sheet, chart, cell range, audio time/channel, video frame, or time range; no caller path/key.
- **Provenance contract:** Principal/scope, document/version, artefact/member, source/derivative hashes, selection coordinates, policy fingerprint, and reason.
- **Bound dimensions:** Selection count, bytes, pages, pixels, cells, duration, frames, tokens, output size, and elapsed time.
- **Locality requirement:** Selection and policy evaluation occur locally; downstream locality is decided separately.
- **Fallback:** Narrow the selection deterministically, use normalised text evidence, or reject if provenance/bounds cannot be established.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** All eight P2-01 use cases.
- **Deferred behaviour:** Automatic whole-document submission and user/model-selected paths or storage keys.
- **P2-03 metadata note:** Catalogue selection dimensions and coordinate types separately from provider/model associations.

### `layout_extraction` — Document layout extraction

- **Capability code:** `layout_extraction`
- **Display name:** Document layout extraction
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Extract ordered text blocks, objects, geometry, and reading-order candidates from a document.
- **Accepted representation:** Inspected PDF or registered page/object representation.
- **Required characteristics:** Digital layout where spatial grouping or reading order may matter.
- **Output evidence:** Structured blocks, coordinates, page/object identifiers, extraction confidence, and ordering metadata.
- **Authority:** Source document owns appearance; extracted tokens/coordinates own only the recorded extraction result.
- **Selection contract:** Bounded page, object, or region range after container inspection.
- **Provenance contract:** Source/derivative hash, page/object coordinates, extractor/version/profile, and output hash.
- **Bound dimensions:** Pages, objects, glyphs, bytes, output records/bytes, and elapsed time.
- **Locality requirement:** Local by default; remote processing requires future approved policy.
- **Fallback:** Plain text extraction with a layout-omission notice, page rendering, or rejection.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PDF-VISUAL`.
- **Deferred behaviour:** Semantic interpretation of diagrams, charts, colour, or visual relationships.
- **P2-03 metadata note:** Represent processor evidence/version and accepted representation associations separately.

### `page_rendering` — Bounded page rendering

- **Capability code:** `page_rendering`
- **Display name:** Bounded page rendering
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Render selected document pages or regions under a fixed raster profile.
- **Accepted representation:** Inspected PDF page/object representation.
- **Required characteristics:** Visual appearance is needed for OCR or bounded specialist evidence.
- **Output evidence:** Registered raster derivative with dimensions, render profile, selected page/region, and hash.
- **Authority:** Source document owns original appearance; derivative owns the exact rendered raster under its profile.
- **Selection contract:** Explicit bounded page and optional rectangular region.
- **Provenance contract:** Source hash, page/region, renderer/version/profile, derivative hash/size, dimensions, and orientation.
- **Bound dimensions:** Source bytes, pages, selected renders, pixels per axis, aggregate pixels, output bytes, and elapsed time.
- **Locality requirement:** Render locally; later specialist locality is a separate decision.
- **Fallback:** Use extracted text/layout evidence with a visual-omission notice or reject.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PDF-SCAN`, `UC-PDF-VISUAL`.
- **Deferred behaviour:** Whole-document unbounded rendering and visual interpretation.
- **P2-03 metadata note:** Keep render profiles/limits processor-specific; do not encode PDF acceptance as behavioural proof.

### `ocr_text_extraction` — OCR text extraction

- **Capability code:** `ocr_text_extraction`
- **Display name:** OCR text extraction
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Recognise text from selected raster evidence and preserve coordinates, confidence, and uncertainty.
- **Accepted representation:** Registered bounded page/image raster or region derivative.
- **Required characteristics:** Missing, incomplete, or unreliable embedded text, or text present only in pixels.
- **Output evidence:** Ordered text spans with bounding boxes, confidence/uncertainty markers, language/profile, and output hash.
- **Authority:** Source pixels own glyph appearance; OCR output owns only the recorded recognition result.
- **Selection contract:** Selected page/image and optional region; no unbounded corpus OCR.
- **Provenance contract:** Source/derivative hashes, coordinates, OCR engine/version/model/profile, preprocessing steps, and output hash.
- **Bound dimensions:** Images/pages, pixels, languages, output characters/bytes, tokens, and elapsed time.
- **Locality requirement:** Local only while sensitivity is `UNMAPPED`.
- **Fallback:** Return partial coordinate-aware OCR with uncertainty, request manual description, or reject.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PDF-SCAN`, `UC-IMAGE-TECHNICAL`.
- **Deferred behaviour:** Treating OCR order as topology or silently correcting uncertain source text.
- **P2-03 metadata note:** Record exact OCR engine/model evidence separately from the stable capability.

### `document_visual_interpretation` — Document visual interpretation

- **Capability code:** `document_visual_interpretation`
- **Display name:** Document visual interpretation
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Explain selected page/region visual relationships using rendered and deterministic evidence.
- **Accepted representation:** Registered bounded page/region raster plus OCR/layout evidence and a scoped question.
- **Required characteristics:** Meaning depends on composition, glyph verification, callouts, diagrams, or other visual relationships.
- **Output evidence:** Structured observations, source coordinates, confidence, uncertainty, and explicit conflicts with deterministic evidence.
- **Authority:** Source render and deterministic extraction remain authoritative; specialist observations are attributed evidence.
- **Selection contract:** Explicit selected pages/regions; never an implicit whole document.
- **Provenance contract:** Source/render hashes, page/region, specialist provider/model/revision, prompt-template fingerprint, and evidence output identity.
- **Bound dimensions:** Images, pixels, input/output tokens, requests, retries, and elapsed time.
- **Locality requirement:** Local and `UNMAPPED`-safe by default; remote ineligible without approved policy.
- **Fallback:** OCR/layout evidence with a visual-omission notice or rejection.
- **Evidence status:** `UNASSESSED`; documented image transport is not behavioural verification.
- **Related use cases:** `UC-PDF-SCAN`, `UC-PDF-VISUAL`.
- **Deferred behaviour:** Direct raw-PDF interpretation and unverified model/provider association.
- **P2-03 metadata note:** Associate exact model/revision, accepted derivatives, evidence state/date/source, and probe result separately.

### `technical_image_interpretation` — Technical image interpretation

- **Capability code:** `technical_image_interpretation`
- **Display name:** Technical image interpretation
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Explain topology, labelled relationships, UI state, or spatial meaning in a selected technical image.
- **Accepted representation:** Verified bounded image/region derivative plus coordinate-aware OCR and a scoped question.
- **Required characteristics:** Spatial, directional, containment, icon, or colour relationships not recoverable from text alone.
- **Output evidence:** Structured entities/relationships with coordinates, confidence, uncertainty, and OCR cross-references.
- **Authority:** Verified pixels and deterministic metadata/OCR remain authoritative for their respective facts.
- **Selection contract:** Whole image only within bounds, otherwise named member and rectangular region.
- **Provenance contract:** Source/derivative hashes, dimensions, region, resize profile, specialist model/revision, and output identity.
- **Bound dimensions:** Encoded bytes, decompressed pixels, regions, input/output tokens, retries, and elapsed time.
- **Locality requirement:** Local only while content is `UNMAPPED`; screenshots may contain sensitive data.
- **Fallback:** Coordinate-aware OCR, manual description, or rejection without invented spatial relationships.
- **Evidence status:** `UNASSESSED`; API image acceptance alone is insufficient.
- **Related use cases:** `UC-IMAGE-TECHNICAL`.
- **Deferred behaviour:** Credential-bearing screenshots, animation/multipage interpretation, and model-selected arbitrary files.
- **P2-03 metadata note:** Store model evidence and image representation associations separately from capability semantics.

### `chart_visual_interpretation` — Chart visual interpretation

- **Capability code:** `chart_visual_interpretation`
- **Display name:** Chart visual interpretation
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Explain visual chart encodings and relationships while grounding numeric claims in deterministic chart/cell data where available.
- **Accepted representation:** Selected chart/page/slide render plus extracted chart metadata and authoritative data series.
- **Required characteristics:** Meaning depends on axes, legends, colour, annotations, layout, or encodings absent from text/CSV.
- **Output evidence:** Attributed interpretation with chart coordinates, referenced data series, confidence, and discrepancies.
- **Authority:** Deterministic data/calculation owns numeric facts; the render owns visual appearance.
- **Selection contract:** One or more explicitly identified bounded charts or chart regions.
- **Provenance contract:** Source/derivative hashes, chart identity, cell/data-series coordinates, render profile, specialist model/revision, and output identity.
- **Bound dimensions:** Charts, series, points, cells, pixels, input/output tokens, and elapsed time.
- **Locality requirement:** Local by default; remote requires approved sensitivity/locality mapping.
- **Fallback:** Deterministic chart metadata/data with a visual-omission notice or rejection.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PDF-VISUAL`, `UC-SPREADSHEET-VISUAL`, `UC-PRESENTATION-VISUAL`.
- **Deferred behaviour:** Model-performed arithmetic and unsupported inference of missing data values.
- **P2-03 metadata note:** Keep chart-render acceptance, data requirements, and exact specialist evidence separate.

### `workbook_structured_extraction` — Workbook structured extraction

- **Capability code:** `workbook_structured_extraction`
- **Display name:** Workbook structured extraction
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Extract workbook, sheet, table, cell, formula, style, chart, and relationship structure under a fixed policy.
- **Accepted representation:** Inspected non-encrypted, non-active XLSX/ODS source container.
- **Required characteristics:** Workbook structure or data is needed beyond existing normalised members.
- **Output evidence:** Registered MANIFEST/TABLE-style structures, formula graph, cached-value status, charts/drawings inventory, and hidden/external-link flags.
- **Authority:** Source workbook owns source structure; deterministic extraction owns its recorded parsed representation.
- **Selection contract:** Workbook inspection followed by bounded sheet, table, cell range, chart, or drawing identity.
- **Provenance contract:** Source hash, sheet/table/cell/chart coordinates, extractor/version/profile, and output-member hashes.
- **Bound dimensions:** Source/expanded bytes, members, sheets, populated cells, formulas, styles, charts, output bytes, and elapsed time.
- **Locality requirement:** Local only while sensitivity is `UNMAPPED`.
- **Fallback:** Existing MANIFEST/CSV when available, or reject unsupported/unsafe workbooks.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-SPREADSHEET-VISUAL`, `UC-OFFICE-ORIGINAL`.
- **Deferred behaviour:** Macro execution, external-link acquisition, embedded active objects, and direct model interpretation of the original.
- **P2-03 metadata note:** Associate source/container representations with this processor separately from calculation and rendering capabilities.

### `spreadsheet_calculation` — Deterministic spreadsheet calculation

- **Capability code:** `spreadsheet_calculation`
- **Display name:** Deterministic spreadsheet calculation
- **Capability class:** `DETERMINISTIC_CALCULATION`
- **Behaviour:** Evaluate approved workbook formulas and derived values under a pinned calculation engine and error policy.
- **Accepted representation:** Validated workbook formula graph and bounded selected cells/ranges from structured extraction.
- **Required characteristics:** User outcome depends on formulas, recalculation, or numeric derivation rather than display alone.
- **Output evidence:** Cell/value/error records with formula lineage, precision/type, engine/version, and calculation status.
- **Authority:** The pinned deterministic calculation result is authoritative for calculated facts; source formulas remain authoritative inputs.
- **Selection contract:** Explicit bounded sheets/cell ranges/formula dependencies; no whole-workbook calculation without policy bounds.
- **Provenance contract:** Source hash, cell/formula coordinates, dependency graph identity, engine/version/options, and result hash.
- **Bound dimensions:** Cells, formulas, dependency depth, iterations, precision, output rows/bytes, and elapsed time.
- **Locality requirement:** Local; no model or remote service may substitute for the calculation engine.
- **Fallback:** Use valid cached values with status disclosure, return uncalculated formulas, or reject.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-SPREADSHEET-VISUAL`.
- **Deferred behaviour:** Macro/custom-function execution, external acquisition, model arithmetic, and silent cached-value trust.
- **P2-03 metadata note:** Catalogue separately from interpretation; engine/version and supported formula profiles belong to processor association metadata.

### `sheet_chart_rendering` — Sheet and chart rendering

- **Capability code:** `sheet_chart_rendering`
- **Display name:** Sheet and chart rendering
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Render selected sheets, tables, ranges, dashboards, or charts under a fixed profile.
- **Accepted representation:** Structured workbook representation plus verified source assets and deterministic calculation results.
- **Required characteristics:** Visual formatting, chart composition, merged layout, or dashboard state matters.
- **Output evidence:** Registered raster/vector derivative with sheet/chart/range identity, dimensions, profile, and hash.
- **Authority:** Source workbook and deterministic cell/calculation data own facts; derivative owns its rendered appearance.
- **Selection contract:** Explicit sheet, chart, table, cell range, or bounded rectangular region.
- **Provenance contract:** Source hash, sheet/chart/cell coordinates, calculation identity, renderer/version/profile, and derivative hash.
- **Bound dimensions:** Sheets/charts, cells, pixels, output bytes, fonts/assets, and elapsed time.
- **Locality requirement:** Render locally; specialist locality is separate.
- **Fallback:** MANIFEST, CSV, chart metadata, and calculations with a visual-omission notice.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-SPREADSHEET-VISUAL`, `UC-OFFICE-ORIGINAL`.
- **Deferred behaviour:** Active-content rendering and direct original-workbook model submission.
- **P2-03 metadata note:** Keep render profiles and accepted workbook representations separate from chart specialist association.

### `presentation_structured_extraction` — Presentation structured extraction

- **Capability code:** `presentation_structured_extraction`
- **Display name:** Presentation structured extraction
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Extract slides, text, notes, objects, grouping, charts, media inventory, and geometry from a presentation.
- **Accepted representation:** Inspected non-encrypted, non-active PPTX/ODP container.
- **Required characteristics:** Slide text/notes or object structure is needed before rendering or interpretation.
- **Output evidence:** Slide/object/notes records with coordinates, order, hidden state, media inventory, and output hash.
- **Authority:** Source presentation owns composition; extraction owns only its recorded structured result.
- **Selection contract:** Bounded slide range, object/region, notes section, or chart identity.
- **Provenance contract:** Source hash, slide/object coordinates, extractor/version/profile, and output-member hashes.
- **Bound dimensions:** Source/expanded bytes, members, slides, objects, notes, charts, media, output bytes, and elapsed time.
- **Locality requirement:** Local only while sensitivity is `UNMAPPED`.
- **Fallback:** Extracted slide text/notes where safely available, or rejection.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PRESENTATION-VISUAL`, `UC-OFFICE-ORIGINAL`.
- **Deferred behaviour:** Animations/build semantics, active objects, external acquisition, and direct original interpretation.
- **P2-03 metadata note:** Associate supported representations and processor evidence separately from rendering/interpretation.

### `slide_rendering` — Bounded slide rendering

- **Capability code:** `slide_rendering`
- **Display name:** Bounded slide rendering
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Render selected slides or regions under a fixed visual profile.
- **Accepted representation:** Structured presentation representation plus verified source assets.
- **Required characteristics:** Composition, diagrams, charts, or image-dependent content is material.
- **Output evidence:** Registered slide/region derivative with dimensions, render profile, and hash.
- **Authority:** Source presentation owns composition; derivative owns its exact rendered appearance under the profile.
- **Selection contract:** Explicit slide and optional object/rectangular region.
- **Provenance contract:** Source hash, slide/object/region, renderer/version/profile, derivative hash/size, and dimensions.
- **Bound dimensions:** Slides, objects, selected renders, pixels, output bytes, fonts/assets, and elapsed time.
- **Locality requirement:** Render locally; downstream specialist locality is separate.
- **Fallback:** Slide text and notes with a visual-omission notice or rejection.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PRESENTATION-VISUAL`, `UC-OFFICE-ORIGINAL`.
- **Deferred behaviour:** Animation execution, embedded active media, and unbounded deck rendering.
- **P2-03 metadata note:** Store render profiles/limits as processor metadata, not as a model capability.

### `presentation_visual_interpretation` — Presentation visual interpretation

- **Capability code:** `presentation_visual_interpretation`
- **Display name:** Presentation visual interpretation
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Explain selected slide composition and relationships using renders, text, notes, and object evidence.
- **Accepted representation:** Registered bounded slide/region render plus structured extraction and scoped question.
- **Required characteristics:** Meaning depends on layout, diagrams, grouping, visual sequence, or notes-to-region relationships.
- **Output evidence:** Structured observations with slide/object coordinates, confidence, uncertainty, and evidence references.
- **Authority:** Source/render and deterministic extraction remain authoritative; specialist output is attributed evidence.
- **Selection contract:** Explicit bounded slide/object/region selection.
- **Provenance contract:** Source/render hashes, slide/object/region, specialist provider/model/revision, prompt-template fingerprint, and output identity.
- **Bound dimensions:** Slides/images, pixels, input/output tokens, retries, and elapsed time.
- **Locality requirement:** Local and remote-ineligible while sensitivity is `UNMAPPED`.
- **Fallback:** Extracted text/notes/object evidence with a visual-omission notice or rejection.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-PRESENTATION-VISUAL`.
- **Deferred behaviour:** Direct Office-container interpretation, animation understanding, and unverified model association.
- **P2-03 metadata note:** Associate exact specialist evidence and derived representations separately.

### `audio_metadata_inspection` — Audio metadata inspection

- **Capability code:** `audio_metadata_inspection`
- **Display name:** Audio metadata inspection
- **Capability class:** `DETERMINISTIC_INSPECTION`
- **Behaviour:** Verify audio container/codec, decoded duration, channels, sample rate, active/nested content, and expansion risk.
- **Accepted representation:** Verified managed audio source resolved by authorised identity.
- **Required characteristics:** Recorded audio is proposed for bounded transcription or analysis.
- **Output evidence:** Codec/container, duration, channels, sample rate, decoded-size estimate, validity, and reason codes.
- **Authority:** Verified audio bytes own samples; inspection owns recorded metadata only.
- **Selection contract:** Inspect the whole bounded outer audio object; emit coordinates for time/channel selection.
- **Provenance contract:** Document/version, source hash/size, inspector/decoder version/profile, and measured metadata.
- **Bound dimensions:** Encoded/decoded bytes, duration, channels, sample rate, nested members, and elapsed time.
- **Locality requirement:** Local only; recordings and voice data remain `UNMAPPED`.
- **Fallback:** Accept an authorised supplied transcript or reject unsupported, malformed, or excessive audio.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** `UC-AUDIO-SPEECH`.
- **Deferred behaviour:** Remote streams, playlists, biometric identity, and reuse of the interactive voice path.
- **P2-03 metadata note:** Keep codec/container associations and decoder limits separate from transcription capability.

### `speech_transcription` — Speech transcription

- **Capability code:** `speech_transcription`
- **Display name:** Speech transcription
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Recognise speech in selected audio and return time-aligned text with uncertainty.
- **Accepted representation:** Validated, locally decoded, bounded audio time/channel selection.
- **Required characteristics:** No authoritative transcript exists and speech content is required for the outcome.
- **Output evidence:** Timestamped segments/words, language, confidence/uncertainty, non-speech markers, and output hash.
- **Authority:** Audio samples remain authoritative; transcript is attributed recognition evidence.
- **Selection contract:** Explicit bounded time range and optional channel; no unbounded recording submission.
- **Provenance contract:** Source/decoded hashes, time/channel coordinates, decoder and transcription engine/model/revision/profile, and output identity.
- **Bound dimensions:** Duration, channels, sample rate, segments, transcript bytes/tokens, retries, and elapsed time.
- **Locality requirement:** Local only until consent, sensitivity, and locality policy is approved.
- **Fallback:** Use an authorised supplied transcript with provenance or reject.
- **Evidence status:** `UNASSESSED`; the interactive Faster Whisper path is not a knowledge capability association.
- **Related use cases:** `UC-AUDIO-SPEECH`, deferred `UC-VIDEO-TEMPORAL` audio tracks.
- **Deferred behaviour:** Remote transcription, biometric identification, and automatic interactive-voice reuse.
- **P2-03 metadata note:** Associate exact transcription model/revision, language/codec limits, evidence state, and effective dates separately.

### `speaker_diarisation` — Speaker diarisation

- **Capability code:** `speaker_diarisation`
- **Display name:** Speaker diarisation
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Partition selected speech into pseudonymous speaker segments without asserting real-world identity.
- **Accepted representation:** Bounded decoded audio plus time-aligned transcription evidence.
- **Required characteristics:** Speaker changes are material and policy permits voice segmentation.
- **Output evidence:** Time ranges with stable within-request speaker labels, confidence, overlap, and uncertainty.
- **Authority:** Audio samples remain authoritative; diarisation labels are attributed evidence, never identity proof.
- **Selection contract:** Explicit bounded time/channel range.
- **Provenance contract:** Source/decoded hashes, time/channel coordinates, diarisation engine/model/revision/profile, and output identity.
- **Bound dimensions:** Duration, channels, speakers, segments, overlap, output bytes, and elapsed time.
- **Locality requirement:** Local only and policy-gated because voice segmentation may be sensitive.
- **Fallback:** Return transcript with unknown speaker labels or omit diarisation explicitly.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** Optional for `UC-AUDIO-SPEECH`.
- **Deferred behaviour:** Speaker identification, biometric matching, enrolment, and remote processing.
- **P2-03 metadata note:** Represent policy eligibility and exact model evidence separately from transcription.

### `audio_semantic_interpretation` — Audio semantic interpretation

- **Capability code:** `audio_semantic_interpretation`
- **Display name:** Audio semantic interpretation
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Interpret selected non-textual audio cues only when they materially affect the scoped outcome.
- **Accepted representation:** Bounded decoded audio plus metadata/transcript and a scoped question.
- **Required characteristics:** Meaning depends on non-speech events, prosody, or acoustic context not represented by transcript text.
- **Output evidence:** Attributed event/observation records with time ranges, confidence, uncertainty, and transcript references.
- **Authority:** Audio samples and deterministic metadata remain authoritative; interpretation is specialist evidence.
- **Selection contract:** Explicit bounded time/channel segment.
- **Provenance contract:** Source/decoded hashes, time/channel, specialist provider/model/revision/profile, and output identity.
- **Bound dimensions:** Duration, channels, events, input/output tokens, retries, and elapsed time.
- **Locality requirement:** Local and policy-gated; remote processing is ineligible while `UNMAPPED`.
- **Fallback:** Transcript/metadata only with an audio-cue omission notice or rejection.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** Optional for `UC-AUDIO-SPEECH`.
- **Deferred behaviour:** Emotion, health, identity, or intent claims without an approved use case and policy.
- **P2-03 metadata note:** Keep acoustic-event scope, policy, and model evidence distinct from transcription.

### `video_metadata_inspection` — Video metadata inspection

- **Capability code:** `video_metadata_inspection`
- **Display name:** Video metadata inspection
- **Capability class:** `DETERMINISTIC_INSPECTION`
- **Behaviour:** Verify video container/codecs, duration, tracks, frame rate, dimensions, subtitles, active content, and expansion risk.
- **Accepted representation:** Verified managed video source resolved by authorised identity.
- **Required characteristics:** Video is proposed for a future bounded derivative path.
- **Output evidence:** Track/container metadata, duration, dimensions, frame rate, subtitle inventory, decoded-size estimate, and reason codes.
- **Authority:** Verified video bytes own encoded source; inspection owns recorded metadata only.
- **Selection contract:** Inspect whole bounded outer container and emit track/time coordinates for later selection.
- **Provenance contract:** Document/version, source hash/size, inspector/decoder version/profile, track identities, and measurements.
- **Bound dimensions:** Source/decoded bytes, duration, tracks, frames, dimensions, frame rate, members, and elapsed time.
- **Locality requirement:** Local only; video processing remains deferred and `UNMAPPED`.
- **Fallback:** Use authorised subtitles/transcript or reject unsupported/unsafe video.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** Deferred `UC-VIDEO-TEMPORAL`.
- **Deferred behaviour:** Full decoding, streaming acquisition, temporal interpretation, and runtime enablement.
- **P2-03 metadata note:** Catalogue now but mark all provider/processor associations inactive/deferred until later approval.

### `subtitle_extraction` — Subtitle extraction

- **Capability code:** `subtitle_extraction`
- **Display name:** Subtitle extraction
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Extract allowlisted embedded or registered sidecar subtitles with timing and track metadata.
- **Accepted representation:** Inspected video subtitle track or separately authorised subtitle artefact.
- **Required characteristics:** Valid subtitle evidence is present and relevant to the outcome.
- **Output evidence:** Time-aligned text cues, language/track identity, style/position metadata where needed, and output hash.
- **Authority:** Source subtitle track/artefact owns cue content; extraction owns its recorded representation.
- **Selection contract:** Explicit subtitle track and bounded time range.
- **Provenance contract:** Video/subtitle source hash, track, cue/time coordinates, extractor/version/profile, and output hash.
- **Bound dimensions:** Tracks, cues, duration, characters/bytes, tokens, and elapsed time.
- **Locality requirement:** Local only while video processing remains deferred and sensitivity is `UNMAPPED`.
- **Fallback:** Use an authorised supplied transcript or omit with notice.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** Deferred `UC-VIDEO-TEMPORAL`.
- **Deferred behaviour:** Remote subtitle acquisition, translation, and temporal visual interpretation.
- **P2-03 metadata note:** Associate subtitle representations/processors separately from speech transcription.

### `keyframe_extraction` — Keyframe extraction

- **Capability code:** `keyframe_extraction`
- **Display name:** Keyframe extraction
- **Capability class:** `DETERMINISTIC_TRANSFORMATION`
- **Behaviour:** Produce policy-bounded frames at explicit or deterministically selected times under a fixed extraction profile.
- **Accepted representation:** Inspected video track and bounded time selection.
- **Required characteristics:** Sparse visual evidence may support a deferred temporal use case without full-video submission.
- **Output evidence:** Registered frame derivatives with timestamps, frame/track coordinates, dimensions, profile, and hashes.
- **Authority:** Source video owns motion/sequence; each derivative owns only its exact extracted frame.
- **Selection contract:** Explicit time/frame list or documented deterministic sampling rule within a bounded range.
- **Provenance contract:** Source hash, track/time/frame coordinates, extractor/version/profile, and derivative hashes.
- **Bound dimensions:** Duration, candidate/selected frames, frame rate, pixels, output bytes, and elapsed time.
- **Locality requirement:** Local only; downstream interpretation remains separately deferred.
- **Fallback:** Transcript/subtitles only or rejection when visual evidence is essential.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** Deferred `UC-VIDEO-TEMPORAL`.
- **Deferred behaviour:** Unbounded frame sampling, motion interpretation, and treating sparse frames as complete temporal evidence.
- **P2-03 metadata note:** Represent sampling profiles and bounds as processor metadata, not model capability.

### `video_temporal_interpretation` — Video temporal interpretation

- **Capability code:** `video_temporal_interpretation`
- **Display name:** Video temporal interpretation
- **Capability class:** `SPECIALIST_INTERPRETATION`
- **Behaviour:** Explain bounded events and changes across time using selected frames, transcript, subtitles, and metadata.
- **Accepted representation:** Registered bounded keyframes/clips plus time-aligned transcript/subtitles and a scoped question.
- **Required characteristics:** The outcome materially depends on motion, ordering, or change that sparse text/static evidence cannot establish.
- **Output evidence:** Attributed event timeline with time/frame coordinates, confidence, uncertainty, and source-evidence references.
- **Authority:** Source video and deterministic time-aligned derivatives remain authoritative; interpretation is attributed evidence.
- **Selection contract:** Explicit bounded time range, tracks, clips/frames, and maximum temporal span.
- **Provenance contract:** Source/derivative hashes, track/time/frame coordinates, specialist provider/model/revision/profile, and output identity.
- **Bound dimensions:** Duration, clips, frames, pixels, audio, input/output tokens, retries, and elapsed time.
- **Locality requirement:** Local only and not eligible for runtime planning until use case, sensitivity, and resource policy are approved.
- **Fallback:** Transcript, subtitles, and bounded keyframes with a temporal-omission notice.
- **Evidence status:** `UNASSESSED`.
- **Related use cases:** Deferred `UC-VIDEO-TEMPORAL`.
- **Deferred behaviour:** The entire capability remains deferred; no provider/model association or runtime path is approved.
- **P2-03 metadata note:** Reserve the stable code but represent no active association; future evidence requires exact model/revision and bounded probe.

## P2-01 mapping matrix

`text_reasoning` is the final response stage for every eligible evidence path.
“Required” means necessary to satisfy the stated future outcome, not currently
implemented and not necessarily deterministic. Optional specialist evidence is
never silently substituted for a required deterministic result.

| Use case | Required behaviours | Optional specialist behaviours | Fallback | Deferred/rejected behaviour | P2-02 posture |
| --- | --- | --- | --- | --- | --- |
| `UC-PDF-SCAN` | `container_inspection`, `bounded_media_selection`, `page_rendering`, `ocr_text_extraction`, `text_reasoning` | `document_visual_interpretation` | OCR text with uncertainty and page/region provenance, or rejection | Raw-PDF/direct unbounded submission rejected | Define; P2-01 remains `CANDIDATE` |
| `UC-PDF-VISUAL` | `container_inspection`, `layout_extraction`, `bounded_media_selection`, `page_rendering`, `text_reasoning` | `document_visual_interpretation`, `chart_visual_interpretation` | Text/layout evidence with visual-omission notice | Direct PDF acceptance is not behavioural proof | Define; P2-01 remains `CANDIDATE` |
| `UC-IMAGE-TECHNICAL` | `container_inspection`, `bounded_media_selection`, `ocr_text_extraction`, `text_reasoning` | `technical_image_interpretation` | Coordinate-aware OCR, manual description, or rejection | Unknown codec, unbounded pixels, and arbitrary attachments rejected | Define; P2-01 remains `CANDIDATE` |
| `UC-SPREADSHEET-VISUAL` | `container_inspection`, `workbook_structured_extraction`, `spreadsheet_calculation`, `bounded_media_selection`, `sheet_chart_rendering`, `text_reasoning` | `chart_visual_interpretation` | MANIFEST, CSV, and deterministic calculations with omission notice | Model arithmetic and active/external workbook behaviour rejected | Define; P2-01 remains `CANDIDATE` |
| `UC-PRESENTATION-VISUAL` | `container_inspection`, `presentation_structured_extraction`, `bounded_media_selection`, `slide_rendering`, `text_reasoning` | `presentation_visual_interpretation`, `chart_visual_interpretation` | Slide text/notes with omission notice or rejection | Direct original-container interpretation deferred | Define; P2-01 remains `CANDIDATE` |
| `UC-AUDIO-SPEECH` | `audio_metadata_inspection`, `bounded_media_selection`, `speech_transcription`, `text_reasoning` | `speaker_diarisation`, `audio_semantic_interpretation` | Authorised supplied transcript or rejection | Optional behaviour evidence-pending; interactive voice reuse rejected | Define transcription; P2-01 remains `CANDIDATE` |
| `UC-VIDEO-TEMPORAL` | If reconsidered: `video_metadata_inspection`, `bounded_media_selection`, `subtitle_extraction`, `speech_transcription`, `keyframe_extraction`, `text_reasoning` | `video_temporal_interpretation` | Transcript, subtitles, bounded keyframes, or rejection | All video processing/runtime association remains deferred | Catalogue stable codes; P2-01 remains `DEFERRED` |
| `UC-OFFICE-ORIGINAL` | `container_inspection` plus the applicable structured extraction/rendering capability; `text_reasoning` consumes only approved derivatives | None by default | Normalised and rendered derivatives | Direct Office-original interpretation remains deferred | Retain P2-01 `DEFERRED` posture |

All P2-01 negative cases remain rejected. Adequate Markdown/CSV replacements,
arbitrary provider-accepted attachments, model-performed spreadsheet
arithmetic, unsafe or encrypted containers, caller-supplied paths or managed
keys, policy-free remote processing, unbounded submission, and reuse of the
interactive voice path acquire no positive capability from this taxonomy.

## Representation and MIME-association rules

MIME acceptance is not behavioural capability evidence. A future association
may state that a processor/API accepts a representation or media type, but it
must not assert that the provider or underlying model performs a behaviour
without the separate dated evidence required below.

- Represent source container, registered derivative, and structured evidence
  as distinct representation kinds.
- Associate MIME types or controlled MIME patterns with an input
  representation and processor/provider association, never directly and
  exclusively with a model or capability route.
- Validate declared MIME against signature, container inspection, registered
  identity, and policy. File extensions are hints only.
- Transport fields such as base64 images, data URLs, file paths accepted by an
  SDK, multipart bodies, or provider file IDs are provider-specific metadata.
  They are not capability codes and never authorise a caller-supplied path.
- A provider may accept an image/PDF/file transport while the exact model lacks
  the required interpretation behaviour. Both API and underlying-model
  evidence are required before routing can be considered.
- Direct Office-container interpretation and raw-PDF interpretation remain
  deferred. Normalised, structured, or rendered derivatives are the default.

## Provider/model evidence states

These states describe one dated provider/model/capability association. They do
not describe runtime enablement, health, locality eligibility, or taxonomy
existence.

- `UNASSESSED`: no adequate dated association evidence has been reviewed.
- `API_DECLARED`: official provider documentation declares a transport or API
  feature, but the exact underlying model behaviour is not verified.
- `MODEL_METADATA_VERIFIED`: a metadata-only query verified the exact model
  identity/revision and declared capability without invoking inference.
- `BOUNDED_PROBE_VERIFIED`: an approved safe fixture and bounded prompt verified
  the exact model/revision against recorded acceptance criteria.
- `REJECTED`: reviewed evidence disproved, contradicted, expired, or failed the
  association; it must not be selected.

Evidence records must include provider/API identity and version where known,
exact model identity and revision, capability code, accepted representation,
source URL or probe identity, checked/effective/expiry dates, state transition,
limits, locality, result, and reviewer. Moving to `BOUNDED_PROBE_VERIFIED`
requires an approved representative fixture, explicit user outcome, safe
expected result, bounded selection, no managed-content reuse, and recorded
model revision. Unavailable or unprobed models remain unverified.

Official Ollama and LM Studio image mechanisms are `API_DECLARED` transport
evidence dated 2026-08-22. They do not promote any capability record or any
registered Orac model to `MODEL_METADATA_VERIFIED` or
`BOUNDED_PROBE_VERIFIED`.

## Authority, provenance, bounds, locality, and fallback

Every later route must preserve this sequence:

```text
authorised document/version identity
    -> verified managed original
    -> deterministic inspection
    -> bounded selection or registered derivative
    -> policy and locality decision
    -> optional verified specialist
    -> structured evidence with source provenance
    -> primary text-response model
```

Mandatory cross-capability rules:

- Caller-supplied paths and managed-store keys are never authority.
- Active, executable, macro-enabled, encrypted, corrupt, unknown, unsupported,
  or excessive content fails closed.
- Source and derivative identities, hashes, coordinates, processor profiles,
  and evidence associations travel with derived facts.
- Bounds are multi-dimensional and policy-owned: bytes alone never substitute
  for members, expansion, pages, pixels, cells, duration, frames, tokens,
  output size, retries, and elapsed time where applicable.
- Local processing is the conservative default but not a sensitivity mapping.
  Remote processing remains ineligible without an approved policy decision.
- Specialist output must be attributed, confidence-bearing, and conflict-aware;
  it never silently replaces a source or deterministic fact.
- Audit metadata includes safe IDs, codes, counts, decisions, evidence state,
  timing, and reason codes. It excludes content, prompts, paths, managed keys,
  transcripts, images, document/spreadsheet labels, and sensitive values.
- Fallback is an explicit narrower representation or rejection. It is never an
  implicit provider switch, policy bypass, whole-document submission, or model
  substitution for deterministic calculation.

## Explicitly rejected capability semantics

The following are not valid capability codes or meanings:

- provider or model names;
- `office_attachment`, generic file/attachment comprehension, or “provider
  accepts files”;
- MIME types, extensions, request fields, base64/data-URL transport, or direct
  MIME-to-model mapping;
- local availability, model registration, enabled flags, health, cost, quality,
  or permission;
- arbitrary filesystem access, caller-managed paths/keys, decryption, macro or
  executable content, external-link acquisition, or unrestricted code;
- unbounded document/media processing, remote eligibility without policy, or
  sensitivity inferred from `DOC_CLASS`;
- model arithmetic, model authority over deterministic facts, speaker identity,
  or reuse of interactive voice as document ingestion.

## P2-03 controlled metadata requirements

P2-03 should design metadata from the following separate concerns without
implementing routing or processors:

### Stable relational concerns

- capability code, display name, class, behaviour summary, active/planning
  state, and effective dates;
- representation kind and controlled MIME/pattern associations;
- provider and concrete model identities without embedding provider names in
  capability semantics;
- provider/model/capability association, evidence state, checked/effective/
  expiry dates, evidence source, exact model revision, and rejection reason;
- bound dimensions and units rather than one overloaded maximum;
- locality classification, processing-policy reference, and explicit remote
  eligibility;
- priority/suitability and availability/health as distinct operational facts;
- selection and provenance contract identifiers;
- immutable audit identity for later association and routing decisions.

### Provider-specific JSON candidates

Provider endpoint paths, request field names, base64/data-URL/multipart shapes,
SDK quirks, provider-native capability labels, quantisation/runtime hints, and
opaque response metadata may remain bounded documented JSON when they are not
used for relational validation, policy, selection, or routing queries. Stable
codes, capability classes, MIME associations, evidence states, locality,
effective dates, and policy limits must not be hidden in JSON.

P2-03 must review compatibility with the existing `llm_registry` and central
reference-domain patterns. It must not infer that the current
`properties.model_type` default proves multimodal behaviour. P2-02 changes no
`llm_registry` row, property, schema object, domain, grant, constraint, seed,
view, package, or Liquibase controller.

## Unresolved evidence and deferred work

- No P2-01 use case is `VALIDATED`; representative fixtures, owners, measured
  expansion, and demonstrated normalisation-insufficient outcomes are missing.
- The local Ollama endpoint remains unavailable for model metadata inspection.
- No exact model identity/revision has `MODEL_METADATA_VERIFIED` or
  `BOUNDED_PROBE_VERIFIED` evidence for the taxonomy.
- Sensitivity, consent, locality, and remote-processing policy is unresolved;
  all P2-01 content remains `UNMAPPED` and remote-ineligible.
- Concrete processor/backend selection, supported formula/codec profiles,
  quality criteria, cost limits, health semantics, and runtime limits remain
  future work.
- Direct Office-original interpretation and `video_temporal_interpretation`
  remain deferred. The stable codes do not make them operational.
- P2-03 model/provider metadata, P2-04 media policy, P2-05 routing, P2-06 binary
  materialisation, P2-07 adapters, and later Phase 2 work remain not started.

## Completion boundary

P2-02 added a planning taxonomy and documentation regression contract only.
Raw-binary and multimodal runtime support remain unavailable. P2-03 metadata
implementation remains deferred and requires separate authorisation. No
runtime capability, database capability, configuration, privilege, provider
adapter, plugin behaviour, managed-store content, model, or deployed service
was added, enabled, downloaded, loaded, or invoked.
