# P2-01 Binary and Multimodal Use-Case Catalogue

Status: completed planning catalogue; no runtime capability is implemented by
this document.

Evidence date: 2026-08-22.

Source plan:
[`orac_document_materialisation_enhancements_plan.md`](orac_document_materialisation_enhancements_plan.md).

## Purpose and Phase 1 boundary

This catalogue records where a future authorised binary or multimodal path may
provide material information that verified normalised Markdown or CSV cannot.
It is evidence for P2-02 capability-taxonomy planning, not an operator guide or
an availability statement.

Phase 1 remains text-only. It retrieves verified UTF-8 Markdown, CSV, plain
text, and JSON; rejects raw-binary materialisation requests; and submits one
bounded prompt string containing untrusted textual evidence. No binary
ingestion route, raw-original materialisation, attachment interface,
multimodal provider adapter, capability router, remote-processing policy, or
Phase 2 runtime behaviour was added by P2-01.

The source binary remains authoritative for its bytes. A deterministic
derivative is authoritative only for the facts it calculates or extracts.
Specialist-model output is evidence and must not silently replace either.

## Authoritative Phase 1 baseline

The following are repository or read-only development-state facts. Hypotheses
begin only in the use-case records.

| Baseline fact | Evidence |
| --- | --- |
| Materialisation accepts only UTF-8 Markdown, CSV, plain text, and JSON, and strictly decodes managed bytes as UTF-8. | `src/orac_core/knowledge/materialisation.py`; `tests/test_knowledge_materialisation.py` |
| A raw-binary request is rejected with `MAT_RAW_BINARY_PHASE1_PROHIBITED`; Phase 1 truncation is prohibited. | `src/orac_core/knowledge/materialisation_policy.py`; `tests/test_knowledge_materialisation_policy.py`; `resources/config/orac.ini` |
| Model evidence is a flat text envelope and the effective model must be `TEXT`. | `src/orac_core/knowledge/model_submission.py`; `tests/test_knowledge_model_submission.py`; `docs/knowledge-model-evidence.md` |
| Provider adapters expose prompt strings and no attachment parameter. Registered provider metadata declares local text-evidence behaviour, not image, document, audio, video, or attachment capability. | `src/model/orac_abc.py`; `src/model/llm_connector.py`; `src/model/provider_registry.py`; `tests/test_llm_connector.py` |
| The active configuration selects local Ollama. The knowledge retrieval, materialisation, and model-evidence stages are independently opt-in. | `resources/config/orac.ini` |
| Drop Box normalises Markdown and text natively and DOCX, HTML, ODT, RTF, and EPUB through Pandoc. PDF, OCR, spreadsheet, presentation, remote acquisition, and embedded-media extraction are not supported. | `plugins/drop_box/docs/drop-box.md`; `plugins/drop_box/docs/drop-box-data-lifecycle.md`; existing Drop Box conversion tests |
| Managed originals are immutable, content-addressed, and reached through controlled identities. Callers and plugins do not receive physical paths. | `src/orac_core/knowledge/managed_store.py`; `src/orac_core/knowledge/retrieval.py`; `docs/document-ingestion.md`; `docs/knowledge-retrieval.md` |
| Normalised sets can contain `PRIMARY`, `MANIFEST`, `TABLE`, and `METADATA` members with hashes, byte sizes, logical names, ordinals, and spreadsheet provenance. This is representational capacity, not a binary converter or submission route. | `resources/db/schema/orac_core/table/knowledge_artefacts.sql`; `resources/db/schema/orac_core/constraint_other/kn_artf_checks.sql`; `resources/db/schema/orac_code/package_body/knowledge_artefact_api.sql` |
| The local voice path uses Faster Whisper for microphone transcription and is not a knowledge-ingestion API. | `src/orac_voice/voice_loop_local.py`; `src/orac_voice/stt_faster_whisper.py`; `resources/config/orac.ini` |
| Current `DOC_CLASS` values describe content purpose and do not constitute privacy, sensitivity, or remote-processing policy. | `resources/db/schema/orac_core/seed_data/document_classifications.sql`; `docs/knowledge-materialisation-policy.md` |
| A read-only development query found 20 enabled model records, all `ollama` with effective `model_type=TEXT`. This inventory does not verify multimodal behaviour. | SQLcl aggregate over `orac_core.llm_registry` on 2026-08-22 |
| A read-only development query found 59 Markdown and one DOCX ingestion request. The DOCX source is 10,632 bytes; Markdown sources range from 1,238 to 87,494 bytes. No PDF, image, spreadsheet, presentation, audio, or video demand was observed. | SQLcl aggregates over `orac_core.knowledge_ingestion_requests` and `orac_core.knowledge_document_versions` on 2026-08-22 |
| The configured Ollama endpoint at `127.0.0.1:11434` was unavailable for a metadata-only model-capability probe. No model was downloaded, loaded, or invoked. | Bounded local `GET /api/tags` probe on 2026-08-22 |

### Evidence-dated provider observations

These observations establish candidate serving mechanisms only. They do not
establish Orac support or prove that any registered underlying model can
perform a use case.

- Ollama's official [vision documentation](https://docs.ollama.com/capabilities/vision)
  says vision models can receive images alongside text, and its official
  [`/api/show` documentation](https://docs.ollama.com/api-reference/show-model-details)
  shows a model-specific capability list. Evidence checked 2026-08-22. The
  serving API mechanism and an individual model's capability must both be
  verified; neither is represented by Orac's current adapter or registry rows.
- LM Studio's official [image-input documentation](https://lmstudio.ai/docs/python/llm-prediction/image-input)
  says selected VLMs accept JPEG, PNG, and WebP through its SDK, while the
  [REST chat API](https://lmstudio.ai/docs/developer/rest/chat) documents an
  image data-URL input. Evidence checked 2026-08-22. Orac's LM Studio adapter
  still submits text strings only, and no concrete local VLM was probed.
- LM Studio's [document-chat documentation](https://lmstudio.ai/docs/app/basics/rag)
  describes adding extracted file content or retrieved text to model context.
  It is not evidence that an underlying model directly comprehends a PDF or
  Office container. Evidence checked 2026-08-22.
- No official provider evidence or local probe established an audio, video,
  Office-container, or raw-PDF backend for Orac during P2-01. Candidate backend
  fields therefore remain unverified where image input alone is insufficient.

## Catalogue contract

### Field definitions

Every positive use-case record contains these fields. `Unknown` and `none
verified` are deliberate evidence states, not omitted values.

| Field | Definition |
| --- | --- |
| Use-case ID | Stable documentation identifier owned by this catalogue. It is not a capability code. |
| Title | Concise user-oriented name. |
| Status | Evidence maturity according to the vocabulary below. |
| Priority | Relative order for further Phase 2 planning, not a delivery commitment. |
| User outcome | The concrete question or task to be completed. |
| Insufficiency trigger | Information lost or made materially unreliable by Markdown or CSV alone. |
| Source media | Expected MIME types and container constraints. |
| Material characteristics | Traits that cause the insufficiency trigger. |
| Authoritative source | Bytes or deterministic derivative that owns each fact. |
| Required selection granularity | Smallest controlled selection needed for processing and provenance. |
| Typical payload | Observed representative measurements, or an explicit evidence gap. |
| Proposed hard bound | Provisional ceiling for later review; never current runtime configuration. |
| Expansion risks | Resource amplification to measure and constrain before processing. |
| Existing content classification | Applicable current `DOC_CLASS` purpose values without sensitivity inference. |
| Sensitivity-policy status | `UNMAPPED`, `LOCAL_ONLY`, `REMOTE_POTENTIALLY_ELIGIBLE`, or `PROHIBITED`. |
| Preferred deterministic processing | Parser, renderer, OCR, transcription, calculation, or metadata operation that runs before any specialist model. |
| Candidate provider class | Provider-neutral optional specialist behaviour. |
| Candidate backend | Concrete evidence-dated option only when API and model evidence are separated. |
| Fallback | Safe result when preferred processing is unavailable or unnecessary. |
| Rejection conditions | Conditions that fail closed rather than downgrade unsafely. |
| Provenance requirement | Coordinates that must accompany every derived fact. |
| Audit requirement | Content-free IDs, decisions, counts, timings, provider class, and reason codes. |
| Current support | Existing reusable components and the missing implementation. |
| Representative fixture | Approved, safe fixture identity, owner, and evidence date, or an explicit gap. |
| Evidence | Repository, query, primary documentation, or measured fixture evidence. |
| Notes for P2-02 | Required behaviour for taxonomy design without creating final capability codes. |

### Status definitions

- `CANDIDATE`: a plausible information-loss case with enough architectural
  evidence to retain, but without both an approved representative fixture and
  a demonstrated user outcome.
- `VALIDATED`: an approved fixture has measured source and expansion
  characteristics, and a recorded user outcome demonstrates that normalised
  Markdown or CSV is inadequate.
- `DEFERRED`: retained for later reconsideration because value, cost, safety,
  demand, or prerequisite evidence is presently insufficient.
- `REJECTED`: binary or multimodal handling is unnecessary or unsafe under the
  stated conditions. Reconsideration requires new evidence and policy review.

P2-01 validates no positive use case. Six remain `CANDIDATE`; two are
`DEFERRED`. Rejected patterns are recorded separately below.

### Priority definitions

- `TIER_1`: first input to P2-02 because the information loss appears material
  and bounded deterministic derivatives are plausible.
- `TIER_2`: useful after Tier 1 semantics and controls are understood.
- `TIER_3`: high cost, low evidence, broad attack surface, or normally
  unnecessary direct-binary behaviour.

Priority does not override status, authorisation, locality, or sensitivity.

### Security and locality interpretation

- `UNMAPPED` is the default because current `DOC_CLASS` values describe
  purpose, not sensitivity. `UNMAPPED` content is ineligible for remote
  processing.
- `LOCAL_ONLY` means an approved policy has explicitly restricted processing
  to controlled local components. No P2-01 record uses it because that policy
  does not yet exist; current candidates are `UNMAPPED` and consequently
  remote-ineligible.
- `REMOTE_POTENTIALLY_ELIGIBLE` can be assigned only by a future approved
  sensitivity and locality policy. No P2-01 record uses it.
- `PROHIBITED` means the characteristic must not enter the proposed path.
- Authorisation begins with document/version identity. A caller-supplied path,
  attachment path, storage key, or fabricated identifier is never authority.
- Diagnostics must not persist source content, images, transcripts, prompts,
  sensitive metadata, managed-store locations, or provider payloads.

## Positive use-case catalogue

### UC-PDF-SCAN — Image-only or poorly OCRed PDF

- **Use-case ID:** `UC-PDF-SCAN`
- **Title:** Recover uncertain text from scanned PDF pages with visual verification.
- **Status:** `CANDIDATE`
- **Priority:** `TIER_1`
- **User outcome:** Answer a question from a scanned document while allowing the user or response model to verify uncertain words against the exact page image.
- **Insufficiency trigger:** Normalised Markdown lacks text for image-only pages and cannot show glyphs, handwriting, stamps, page structure, or OCR uncertainty needed to resolve ambiguous text.
- **Source media:** `application/pdf`; one non-encrypted, structurally valid PDF container with no active or embedded executable content.
- **Material characteristics:** Raster-only or mixed pages, skew, low contrast, handwriting, stamps, multi-column scans, and uncertain OCR.
- **Authoritative source:** The verified PDF owns source bytes and visual appearance; deterministic OCR output owns recognised text plus confidence/uncertainty metadata, never the original glyphs.
- **Required selection granularity:** Document inspection, then bounded page and region selections; never automatic whole-document model submission.
- **Typical payload:** Observed: no approved representative fixture or PDF demand in the development corpus; bytes, page count, pixels, and OCR output are unknown.
- **Proposed hard bound:** Planning ceiling only: 25 MiB source, 100 pages inspected, at most 20 selected rendered pages per request, 4,096 pixels on either rendered-page axis, and 80 megapixels aggregate selected raster area. These are conservative starting points, not fixture-derived runtime settings.
- **Expansion risks:** PDF object streams, embedded images/fonts, page rendering, pixel bombs, malformed cross-references, OCR CPU/memory use, and output text growth.
- **Existing content classification:** Any applicable current purpose code (`RAW_REFERENCE`, `CONCISE_KNOWLEDGE_NOTE`, `IMPLEMENTATION_DECISION_RECORD`, `TECHNICAL_MANUAL`, `TROUBLESHOOTING_NOTE`, or `AUTOMATION_RULE_NOTE`); no code implies sensitivity.
- **Sensitivity-policy status:** `UNMAPPED`; deterministic processing is local by default and remote submission remains ineligible until P2-05 or another approved policy maps sensitivity and locality.
- **Preferred deterministic processing:** Local signature/container inspection, page counting, bounded rendering, image preprocessing, and OCR with confidence or uncertainty markers.
- **Candidate provider class:** Optional local document-vision interpreter over selected rendered pages and OCR evidence.
- **Candidate backend:** None verified. Ollama and LM Studio document image-input mechanisms as of 2026-08-22, but Orac has no attachment adapter and no locally probed registered vision model.
- **Fallback:** Return OCR-derived text with uncertainty markers and page/region provenance; reject when text remains unreadable or the user outcome depends on omitted visual evidence.
- **Rejection conditions:** Unauthorised identity, encryption/password protection, corrupt or malformed PDF, active content, excessive page/object/pixel expansion, unsupported codecs, missing page provenance, or processing outside the locality decision.
- **Provenance requirement:** Document version, source hash, page number, rendered derivative hash and profile, region coordinates, OCR engine/version, and uncertainty markers.
- **Audit requirement:** Safe document/version IDs, decision and reason code, inspected/selected page counts, source/rendered byte and pixel counts, processor/provider class, locality, and timings; no page image, text, path, or prompt.
- **Current support:** Managed-store verification, authorised identities, artefact descriptors, and a page-range policy vocabulary are reusable. PDF inspection, rendering, OCR artefacts, region provenance, and specialist routing are missing.
- **Representative fixture:** None approved; owner unresolved; fixture and user-outcome evidence required before `VALIDATED`.
- **Evidence:** Phase 1 baseline above; `docs/knowledge-materialisation-policy.md`; no PDF rows in the 2026-08-22 development inventory.
- **Notes for P2-02:** Distinguish deterministic PDF inspection/render/OCR behaviours from optional selected-page visual interpretation and require page/region selection plus local-only eligibility.

### UC-PDF-VISUAL — Visually complex digital PDF

- **Use-case ID:** `UC-PDF-VISUAL`
- **Title:** Interpret layout-dependent evidence in a digital PDF.
- **Status:** `CANDIDATE`
- **Priority:** `TIER_1`
- **User outcome:** Explain a chart, diagram, callout, or reading-order relationship whose meaning depends on the rendered page.
- **Insufficiency trigger:** Extracted Markdown can lose spatial grouping, arrows, legends, colour, overlay order, marginal callouts, diagram topology, and intended reading sequence.
- **Source media:** `application/pdf`; bounded, non-encrypted digital PDF with allowlisted renderable features.
- **Material characteristics:** Positioned text, vector diagrams, charts, annotations, multi-column layout, callouts, and image/text composition.
- **Authoritative source:** The verified PDF owns rendered appearance; deterministic text/layout extraction owns extracted tokens and coordinates; deterministic chart data, when recoverable, owns numeric values.
- **Required selection granularity:** Page, region, chart, or diagram selected after deterministic inspection.
- **Typical payload:** Observed: no approved representative fixture or PDF demand in the development corpus; source, render, and selection measurements are unknown.
- **Proposed hard bound:** Planning ceiling only: 25 MiB source, 150 pages inspected, at most 20 selected page/region renders, 4,096 pixels per axis, and 80 megapixels aggregate selected raster area; not runtime configuration.
- **Expansion risks:** Complex vector rendering, transparency, embedded fonts/images, page-object count, high-DPI rasterisation, nested forms, and aggregate visual tokens.
- **Existing content classification:** Any applicable current `DOC_CLASS` purpose code; classification does not establish sensitivity or remote eligibility.
- **Sensitivity-policy status:** `UNMAPPED`; deterministic processing is local by default and remote processing is ineligible.
- **Preferred deterministic processing:** Local PDF validation, text/layout extraction, object/page metadata, bounded page rendering, and deterministic chart-data extraction where possible.
- **Candidate provider class:** Optional local page/diagram/chart interpreter over selected derivatives and deterministic evidence.
- **Candidate backend:** None verified. Official Ollama and LM Studio image mechanisms were reviewed on 2026-08-22, but no registered local model or Orac route was verified for PDF-derived page interpretation.
- **Fallback:** Return normalised text and deterministic layout metadata with an explicit notice that selected visual evidence was omitted; reject if that omission defeats the requested outcome.
- **Rejection conditions:** Unauthorised, encrypted, malformed, active, excessive object/page/pixel expansion, unsupported renderer feature, unregistered derivative, missing coordinates, or prohibited locality.
- **Provenance requirement:** Document version and source hash; page and region; renderer/profile/version; derivative hash; extracted object coordinates; chart/diagram identity where present.
- **Audit requirement:** Safe IDs, decision/reason, inspected and selected pages/regions, byte/object/pixel counts, processor/provider class, locality, and timings without content or paths.
- **Current support:** Authorised identity, verified reads, normalised evidence, artefact hashes, and page-range selectors are reusable. PDF layout extraction, rendering, visual derivative registration, and interpretation routing are missing.
- **Representative fixture:** None approved; owner unresolved; a layout-dependent question and measured PDF are required before `VALIDATED`.
- **Evidence:** Phase 1 baseline above; `src/orac_core/knowledge/materialisation_policy.py`; no PDF rows in the 2026-08-22 development inventory.
- **Notes for P2-02:** Separate deterministic document layout/rendering and chart extraction from optional page, diagram, or chart interpretation; preserve explicit page/region provenance.

### UC-IMAGE-TECHNICAL — Diagram, screenshot, or technical image

- **Use-case ID:** `UC-IMAGE-TECHNICAL`
- **Title:** Interpret a bounded technical image.
- **Status:** `CANDIDATE`
- **Priority:** `TIER_1`
- **User outcome:** Explain topology, labelled relationships, error state, or interface layout shown only in a diagram or screenshot.
- **Insufficiency trigger:** OCR text does not preserve arrow direction, containment, proximity, colour-coded state, visual hierarchy, or which label belongs to which component.
- **Source media:** `image/png`, `image/jpeg`, and `image/webp`; TIFF only after separate codec, multipage, and decompression review.
- **Material characteristics:** Diagrams, screenshots, labels, icons, connectors, topology, small text, colour state, and spatial relationships.
- **Authoritative source:** Verified image bytes own pixels; deterministic metadata owns dimensions/encoding; OCR owns recognised characters with coordinates and uncertainty.
- **Required selection granularity:** Whole image only when bounded, otherwise named image member and rectangular region.
- **Typical payload:** Observed: no approved image fixture or image demand in the development corpus; bytes, dimensions, and decompressed pixels are unknown.
- **Proposed hard bound:** Planning ceiling only: 15 MiB encoded source, 8,192 pixels per axis, 40 megapixels decompressed per image, at most 8 selected images or regions and 80 megapixels aggregate per request; not runtime configuration.
- **Expansion risks:** Decompression bombs, oversized dimensions, multi-frame images, metadata/profile parsing, alpha layers, animation, malformed codecs, and OCR/vision memory use.
- **Existing content classification:** Any applicable current `DOC_CLASS` purpose code; it is not a sensitivity classification.
- **Sensitivity-policy status:** `UNMAPPED`; screenshots may contain credentials or personal data, deterministic processing is local by default, and remote processing remains ineligible.
- **Preferred deterministic processing:** Signature and codec validation, metadata stripping/inspection without changing authority, decompressed-pixel accounting, orientation handling, and local OCR with coordinates.
- **Candidate provider class:** Optional local technical-vision interpreter constrained to selected images/regions and user-stated questions.
- **Candidate backend:** None verified. Official Ollama and LM Studio documentation reviewed 2026-08-22 describes image input, but no Orac adapter or registered underlying model was verified; LM Studio documents JPEG/PNG/WebP specifically.
- **Fallback:** Return coordinate-aware OCR or request a manual description; never invent missing spatial relationships or silently treat OCR order as topology.
- **Rejection conditions:** Unauthorised identity, unknown/disallowed codec, malformed image, animation or multipage form not explicitly supported, excessive encoded/decompressed size, credentials detected by approved policy, missing region provenance, or disallowed locality.
- **Provenance requirement:** Document/version and member identity, source/derivative hash, image dimensions/orientation, region coordinates, OCR engine/version, and any resize profile.
- **Audit requirement:** Safe IDs, decision/reason, MIME signature, encoded bytes, dimensions/pixels, selected region count, processor/provider class, locality, and timings; no pixels, OCR text, paths, or prompt.
- **Current support:** Managed immutable bytes and artefact descriptors are reusable. Image allowlisting, pixel accounting, OCR artefacts, region selectors, sensitivity controls, and vision routing are missing.
- **Representative fixture:** None approved; owner unresolved; a safe technical image plus spatial question is required before `VALIDATED`.
- **Evidence:** Phase 1 baseline and provider observations above; no image rows in the 2026-08-22 development inventory.
- **Notes for P2-02:** Describe metadata/pixel validation, OCR, and optional technical spatial interpretation separately; do not define capability semantics by provider name or file extension alone.

### UC-SPREADSHEET-VISUAL — Workbook charts or layout-dependent tables

- **Use-case ID:** `UC-SPREADSHEET-VISUAL`
- **Title:** Interpret workbook charts, dashboards, and layout cues.
- **Status:** `CANDIDATE`
- **Priority:** `TIER_1`
- **User outcome:** Explain a chart trend, dashboard state, merged visual table, or formatting cue that is not represented by MANIFEST and CSV members.
- **Insufficiency trigger:** CSV and manifest evidence can omit chart series/style, axis/legend association, conditional formatting, merged-region presentation, drawing placement, and dashboard composition.
- **Source media:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (XLSX) and `application/vnd.oasis.opendocument.spreadsheet` (ODS); no macros or encrypted containers.
- **Material characteristics:** Formulas and cached values, multiple sheets, charts, dashboards, merged cells, conditional formatting, drawings, hidden state, and layout-dependent tables.
- **Authoritative source:** Verified workbook owns source bytes and presentation; a deterministic workbook engine owns parsed cells/formulas and calculated values; deterministic MANIFEST/TABLE members own their extracted structures. A model is never authoritative for arithmetic.
- **Required selection granularity:** Workbook inspection followed by sheet, table, cell range, chart, or bounded rendered region.
- **Typical payload:** Observed: no approved workbook fixture or workbook demand in the development corpus; bytes, sheet count, cell count, chart count, and rendered size are unknown.
- **Proposed hard bound:** Planning ceiling only: 25 MiB source, 100 sheets, 1,000,000 populated cells inspected, 20 selected sheets/charts, 4,096 pixels per rendered axis, and 80 megapixels aggregate selected raster area; not runtime configuration and subject to fixture measurement.
- **Expansion risks:** ZIP expansion, shared strings/styles, formula graphs, external links, embedded objects, images, large sparse ranges, chart caches, render memory, and calculation time.
- **Existing content classification:** Any applicable current `DOC_CLASS` purpose code; no sensitivity or remote-processing meaning is inferred.
- **Sensitivity-policy status:** `UNMAPPED`; deterministic processing is local by default and remote submission is ineligible without an approved policy.
- **Preferred deterministic processing:** Container and macro inspection, deterministic workbook parsing, formula/calculation policy, MANIFEST/TABLE production, chart metadata extraction, and bounded sheet/chart rendering.
- **Candidate provider class:** Optional local chart or layout interpreter over selected renders plus authoritative deterministic cell/chart data.
- **Candidate backend:** None verified. Reviewed image-input mechanisms are only candidate transport for rendered derivatives; no provider or underlying model was verified for workbook semantics.
- **Fallback:** Return MANIFEST and CSV evidence, deterministic calculations, and an explicit notice that visual chart/layout evidence was omitted.
- **Rejection conditions:** Unauthorised, encrypted, macro-enabled or active content, external links requiring acquisition, corrupt/unsafe ZIP, excessive expansion/cells/formula depth/rendering, unsupported embedded objects, or model-requested arithmetic substitution.
- **Provenance requirement:** Document/version, workbook hash, sheet, table/cell range, chart/drawing identity, formula/calculation engine and version, render profile, and derivative hash.
- **Audit requirement:** Safe IDs, decision/reason, workbook bytes, expanded bytes, sheet/cell/chart counts, selected ranges/renders, processor/provider class, locality, and timings without cells, formulas, paths, or images.
- **Current support:** Artefact roles, spreadsheet MANIFEST/TABLE provenance fields, table selections, and deterministic CSV chunking are reusable. Workbook conversion, calculation, chart extraction/rendering, and specialist interpretation are missing.
- **Representative fixture:** None approved; owner unresolved; a safe workbook with a chart-dependent question and measured expansion is required before `VALIDATED`.
- **Evidence:** `docs/document-ingestion.md`; `resources/db/schema/orac_code/package_body/knowledge_artefact_api.sql`; `src/orac_core/knowledge/csv_chunking.py`; no workbook rows in the 2026-08-22 development inventory.
- **Notes for P2-02:** Keep workbook parsing/calculation, sheet/chart rendering, and optional visual interpretation distinct; make deterministic arithmetic authority and chart/cell provenance mandatory behaviours.

### UC-PRESENTATION-VISUAL — Slides with layout or embedded graphics

- **Use-case ID:** `UC-PRESENTATION-VISUAL`
- **Title:** Interpret visual composition in presentation slides.
- **Status:** `CANDIDATE`
- **Priority:** `TIER_2`
- **User outcome:** Explain a slide diagram, composition, or speaker-context relationship that extracted slide text and notes cannot convey.
- **Insufficiency trigger:** Markdown can lose object placement, builds, arrows, layered diagrams, grouping, background meaning, image-dependent content, and the relationship between notes and a slide region.
- **Source media:** `application/vnd.openxmlformats-officedocument.presentationml.presentation` (PPTX), `application/vnd.oasis.opendocument.presentation` (ODP), or a separately validated PDF slide derivative; no macro-enabled formats.
- **Material characteristics:** Slides, notes, master/layout inheritance, diagrams, charts, embedded graphics/media, grouping, and visual sequence.
- **Authoritative source:** Verified presentation owns original composition; deterministic extraction owns text/notes and object coordinates; bounded rendered slides own selected visual derivatives.
- **Required selection granularity:** Presentation inspection followed by slide, object/region, notes section, or chart selection.
- **Typical payload:** Observed: no approved presentation fixture or presentation demand in the development corpus; bytes, slides, objects, and rendered pixels are unknown.
- **Proposed hard bound:** Planning ceiling only: 50 MiB source, 200 slides inspected, 30 selected slide/region renders, 4,096 pixels per axis, and 120 megapixels aggregate selected raster area; not runtime configuration.
- **Expansion risks:** ZIP expansion, embedded media/objects/fonts, master inheritance, vector rendering, high-resolution images, animations, and aggregate rendered pixels.
- **Existing content classification:** Any applicable current `DOC_CLASS` purpose code; it does not determine sensitivity.
- **Sensitivity-policy status:** `UNMAPPED`; local deterministic inspection only is presumed, and all remote processing remains ineligible.
- **Preferred deterministic processing:** Container/active-content inspection, slide/text/notes/object extraction, embedded-media inventory, and bounded slide/region rendering.
- **Candidate provider class:** Optional local slide/diagram interpreter over selected renders and extracted text/notes.
- **Candidate backend:** None verified. Image-capable serving mechanisms are evidence-dated candidates for slide renders only; no presentation backend or registered model was verified.
- **Fallback:** Return extracted slide text and notes with slide provenance and an explicit notice that visual evidence was omitted; reject when visual composition is essential.
- **Rejection conditions:** Unauthorised, encrypted, macro-enabled, active or externally linked content, corrupt container, excessive expansion/slides/objects/pixels, unsupported embedded media, or missing slide/region provenance.
- **Provenance requirement:** Document/version, source hash, slide number, notes/object/region identity, renderer profile/version, and derivative hash.
- **Audit requirement:** Safe IDs, decision/reason, bytes, expanded size, inspected/selected slide and object counts, pixels, processor/provider class, locality, and timings without content or paths.
- **Current support:** Managed originals and generic artefact descriptors are reusable. Presentation inspection, extraction, rendering, slide provenance, and routing are missing; Drop Box does not support presentations.
- **Representative fixture:** None approved; owner unresolved; a visual-dependent slide outcome and measured safe fixture are required before `VALIDATED`.
- **Evidence:** Phase 1 baseline above; `plugins/drop_box/docs/drop-box.md`; no presentation rows in the 2026-08-22 development inventory.
- **Notes for P2-02:** Separate deterministic slide extraction/rendering from optional visual interpretation and require slide/object/region selection.

### UC-AUDIO-SPEECH — Recorded speech requiring transcription

- **Use-case ID:** `UC-AUDIO-SPEECH`
- **Title:** Transcribe an authorised bounded speech recording.
- **Status:** `CANDIDATE`
- **Priority:** `TIER_2`
- **User outcome:** Search, quote with time provenance, or answer from recorded speech when no authoritative transcript exists.
- **Insufficiency trigger:** Markdown cannot be created reliably without decoding and transcription, and supplied prose may omit uncertainty, speaker changes, or time alignment.
- **Source media:** Allowlisted PCM WAV and FLAC first; MP3 and M4A only after codec/container validation. No playlists, remote streams, or nested media containers.
- **Material characteristics:** Speech, silence, noise, accents, multiple speakers, codec variation, and time-dependent utterances; diarisation is a separate optional requirement.
- **Authoritative source:** Verified audio owns samples; deterministic metadata owns codec/duration; transcription output owns recognised words plus timestamps and uncertainty, not the original speech signal.
- **Required selection granularity:** Whole bounded clip for inspection, then time range and optional channel/speaker segment.
- **Typical payload:** Observed: no approved knowledge-audio fixture or audio demand in the corpus. Interactive voice is configured for 16 kHz input and at most 20 seconds, but that runtime measurement is not representative of knowledge audio.
- **Proposed hard bound:** Planning ceiling only: 100 MiB source, 60 minutes decoded duration, at most two channels, 48 kHz input, and 2 MiB transcript/segment metadata; not runtime configuration and not copied from interactive voice limits.
- **Expansion risks:** Codec decoding, sample-rate/channel expansion, long silence, malformed headers, duration spoofing, transcription compute/memory, segment count, and retained temporary audio.
- **Existing content classification:** Any applicable current `DOC_CLASS` purpose code; it does not express consent, personal-data sensitivity, or voice-biometric policy.
- **Sensitivity-policy status:** `UNMAPPED`; deterministic processing is local by default, and recordings and transcripts are ineligible for remote processing.
- **Preferred deterministic processing:** Signature/codec/duration inspection, bounded local decoding, speech detection, and local transcription with time ranges and uncertainty. Diarisation, if justified, remains separate.
- **Candidate provider class:** Local speech-to-text processor; optional local diarisation or audio-understanding specialist only after separate evidence.
- **Candidate backend:** Faster Whisper is implementation evidence for local transcription, not a knowledge-ingestion backend. No end-to-end backend or model registration was verified for this use case.
- **Fallback:** Use an authorised supplied transcript with provenance, or reject; never route through the interactive microphone path as a shortcut.
- **Rejection conditions:** Unauthorised, encrypted/DRM, unknown codec, remote stream, excessive bytes/duration/channels/sample rate, malformed duration, missing consent/policy where required, unsupported language, or unavailable local processor.
- **Provenance requirement:** Document/version and audio hash, codec/channel metadata, time range for every segment, transcription engine/model/version, language decision, and confidence/uncertainty.
- **Audit requirement:** Safe IDs, decision/reason, source bytes, decoded duration/channels/sample rate, segment count, processor/provider class, locality, and timings without samples, transcript, paths, or prompt.
- **Current support:** Local Faster Whisper microphone transcription shows a reusable processor class. Knowledge-audio authorisation, managed derivative registration, duration policy, transcript provenance, and ingestion routing are missing.
- **Representative fixture:** None approved; owner unresolved; a redistributable speech clip plus transcript-dependent user outcome is required before `VALIDATED`.
- **Evidence:** `src/orac_voice/voice_loop_local.py`; `src/orac_voice/stt_faster_whisper.py`; `resources/config/orac.ini`; no audio rows in the 2026-08-22 development inventory.
- **Notes for P2-02:** Distinguish bounded deterministic metadata/decoding and speech transcription from optional diarisation or broader audio understanding; require time-range provenance and local-only eligibility.

### UC-VIDEO-TEMPORAL — Video requiring temporal evidence

- **Use-case ID:** `UC-VIDEO-TEMPORAL`
- **Title:** Correlate speech, selected frames, and events over time.
- **Status:** `DEFERRED`
- **Priority:** `TIER_3`
- **User outcome:** Answer a concrete question requiring the temporal relationship between speech, visible state, and an event that a transcript plus bounded keyframes cannot answer.
- **Insufficiency trigger:** Markdown loses motion, ordering, timing, and cross-modal correlation; however no current outcome demonstrates that transcript and selected keyframes are insufficient.
- **Source media:** Separately allowlisted MP4, WebM, or MOV codec profiles only; no remote streams, playlists, or unknown containers.
- **Material characteristics:** Audio tracks, frame sequences, motion, scene changes, subtitles, multiple codecs, and time-correlated events.
- **Authoritative source:** Verified video owns encoded audiovisual evidence; deterministic metadata owns streams/duration; transcript owns recognised timed speech; extracted frames own pixels at exact timestamps.
- **Required selection granularity:** Stream, time range, subtitle track, and bounded keyframe/frame selection; never an unbounded whole video.
- **Typical payload:** Observed: no approved fixture, corpus demand, or user outcome. Source bytes, duration, decoded frames, and derivative sizes are unknown.
- **Proposed hard bound:** Planning ceiling for future review only: 500 MiB source, 30 minutes duration, 120 selected keyframes, 4,096 pixels per frame axis, and 120 megapixels aggregate selected frames; no implementation should adopt these values without fixture evidence.
- **Expansion risks:** Codec decode, frame-rate and resolution multiplication, multiple streams, variable duration metadata, subtitles, keyframe extraction, temporary storage, GPU/CPU contention, and aggregate visual tokens.
- **Existing content classification:** Any applicable current `DOC_CLASS` purpose code; it provides no audiovisual privacy, consent, or sensitivity decision.
- **Sensitivity-policy status:** `UNMAPPED`; remote processing is ineligible and no processing route is approved.
- **Preferred deterministic processing:** Container/stream metadata, duration validation, subtitle extraction, bounded audio transcription, scene-change detection, and deterministic keyframe selection before any specialist processing.
- **Candidate provider class:** Optional local temporal or cross-modal interpreter over a selected time range, transcript, and bounded frames.
- **Candidate backend:** None verified. P2-01 found no official/local backend evidence sufficient for an Orac video route.
- **Fallback:** Transcript, subtitles, and selected keyframes with explicit limits; reject or request a narrower question when those derivatives cannot answer safely.
- **Rejection conditions:** No concrete derivative-insufficient outcome, unauthorised identity, remote source, unknown/disallowed codecs, excessive bytes/duration/streams/frames/pixels, malformed timestamps, DRM/encryption, active content, or unavailable local deterministic processors.
- **Provenance requirement:** Document/version and source hash, stream/track identity, exact time ranges, frame timestamps, transcript segments, extraction profiles/versions, and derivative hashes.
- **Audit requirement:** Safe IDs, decision/reason, stream/duration/frame/keyframe/pixel counts, selected time ranges, processor/provider class, locality, and timings without media, transcript, paths, or prompt.
- **Current support:** Managed bytes, textual evidence, and local speech transcription concepts are reusable. Video validation, decoding, keyframe/transcript artefacts, temporal provenance, and routing are missing.
- **Representative fixture:** None approved; owner unresolved. A concrete question not answerable by transcript and bounded keyframes is required even to reconsider priority.
- **Evidence:** Phase 1 baseline above; no video rows in the 2026-08-22 development inventory; no concrete provider backend verified.
- **Notes for P2-02:** Retain temporal selection and derivative composition as future taxonomy inputs, but do not make whole-video submission or a stable video capability code implementation-ready.

### UC-OFFICE-ORIGINAL — Direct Office-binary interpretation

- **Use-case ID:** `UC-OFFICE-ORIGINAL`
- **Title:** Direct interpretation of an Office original when derivatives cannot preserve essential embedded or layout evidence.
- **Status:** `DEFERRED`
- **Priority:** `TIER_3`
- **User outcome:** Resolve an explicitly identified layout or embedded-object question that safe deterministic text, tables, metadata, and renders cannot represent.
- **Insufficiency trigger:** No current user outcome establishes this need. Direct binary interpretation is unnecessary when deterministic normalisation and bounded derivatives preserve the requested information.
- **Source media:** Inactive DOCX, XLSX, PPTX, ODT, ODS, or ODP only after format-specific review; macro-enabled formats, encrypted containers, and active content are excluded.
- **Material characteristics:** ZIP/package relationships, styles, layouts, drawings, charts, embedded objects, tracked changes, notes, and potentially active/external content.
- **Authoritative source:** Verified Office container owns source bytes; deterministic parser/calculation/render outputs own extracted or calculated facts; any specialist result remains secondary evidence.
- **Required selection granularity:** Named package member, page/slide/sheet, object, chart, region, table, or cell range; arbitrary whole-original submission is not justified.
- **Typical payload:** Observed: one 10,632-byte DOCX request exists in development, but no approved fixture or outcome shows that its normalised Markdown is inadequate. No spreadsheet or presentation source was observed.
- **Proposed hard bound:** No direct-submission bound is approved. A future inspection-only planning ceiling may start at 50 MiB source, 500 MiB expanded package, 10,000 package members, and the narrower media-specific page/sheet/slide/image bounds above; all require fixture review before configuration.
- **Expansion risks:** ZIP bombs, path traversal, relationship recursion, macros, OLE/embedded executables, external links, encrypted members, large media, formula graphs, and renderer/parser vulnerabilities.
- **Existing content classification:** Any applicable current `DOC_CLASS` purpose code; it does not authorise embedded content, remote processing, or disclosure.
- **Sensitivity-policy status:** `UNMAPPED`; remote processing is ineligible and active content is `PROHIBITED`.
- **Preferred deterministic processing:** Format-specific package validation, active-content inventory, parser, calculation where applicable, embedded-object inventory, and bounded rendering/normalisation first.
- **Candidate provider class:** None by default. Only a future specialist operating on approved deterministic derivatives should be considered unless a fixture proves direct container access essential.
- **Candidate backend:** None verified. LM Studio document chat describes textual context/RAG, not underlying-model Office-container comprehension; no raw-Office Orac backend was verified on 2026-08-22.
- **Fallback:** Use verified Markdown, MANIFEST/TABLE members, extracted notes, metadata, and bounded renders; reject when the requested outcome depends on unsafe or unsupported embedded content.
- **Rejection conditions:** Adequate deterministic representation, arbitrary attachment request, unauthorised identity, macros, active/executable content, encryption/password protection, unknown container, unsafe package paths, excessive expansion/members/embedded media, external acquisition, or missing selection/provenance.
- **Provenance requirement:** Document/version and source hash, package member, page/slide/sheet/object/chart/table/cell/region as applicable, processor/version, and derivative hash.
- **Audit requirement:** Safe IDs, decision/reason, source/expanded bytes, package member and embedded-object counts, selected derivative coordinates, processor/provider class, locality, and timings without content, member names that leak paths, or prompt.
- **Current support:** Drop Box can normalise several document formats and Core can register normalised artefacts. Spreadsheet/presentation support, safe embedded-object handling, render derivatives, and any direct-binary submission path are missing.
- **Representative fixture:** None approved. The 10,632-byte development DOCX is inventory evidence only and is not an approved redistributable fixture or demonstrated direct-binary use case.
- **Evidence:** `plugins/drop_box/docs/drop-box.md`; `docs/document-ingestion.md`; 2026-08-22 development inventory; LM Studio document-chat documentation checked 2026-08-22.
- **Notes for P2-02:** Treat safe package inspection and deterministic format-specific derivatives as separate behaviours. Do not create a generic Office-attachment semantic or direct provider mapping without a validated exception.

## Explicitly rejected or unnecessary binary cases

The following patterns are `REJECTED` for P2-01. They are not additional
positive use cases and have no priority tier.

| Rejected pattern | Why binary or multimodal submission is unjustified | Safe behaviour |
| --- | --- | --- |
| Verified Markdown or CSV already answers the user outcome | Binary processing adds risk and cost without recovering material information. | Use the authorised normalised evidence. |
| Arbitrary file accepted by a provider API | Transport acceptance does not prove underlying-model comprehension, safety, or Orac authorisation. | Require a catalogued use case, verified model, policy decision, and bounded derivative. |
| Spreadsheet arithmetic or aggregation | Deterministic parsing and calculation are authoritative and reproducible. | Calculate deterministically and optionally ask a model to explain cited results. |
| Archive, executable, macro-enabled active content, or unknown container | Expansion, execution, traversal, and parser risks exceed the catalogue's evidence. | Reject; do not inspect through a model. |
| Encrypted or password-protected content | No separately authorised recovery/decryption workflow exists. | Fail closed without requesting or logging passwords. |
| Caller-supplied filesystem path or managed-store key | Paths and keys bypass controlled identity and authorisation boundaries. | Resolve only authorised document/version/artefact identities inside Core. |
| Remote processing without approved sensitivity/locality | Current content classification does not authorise disclosure. | Keep remote processing ineligible. |
| Unbounded whole document, workbook, audio, or video | Resource, privacy, context, and provenance risks cannot be controlled. | Inspect deterministically and require bounded page/region/sheet/chart/time/frame selection. |
| Interactive voice path reused for knowledge ingestion | Microphone transcription has different authority, persistence, provenance, and duration boundaries. | Build a separately authorised knowledge-audio path in a future stage or reject. |
| Direct Office original when deterministic derivatives suffice | The container provides no additional necessary user outcome. | Use verified normalisation and bounded renders/metadata. |

## Evidence sources and unresolved gaps

### Repository evidence

- `docs/document-ingestion.md`
- `docs/knowledge-retrieval.md`
- `docs/knowledge-materialisation-policy.md`
- `docs/knowledge-model-evidence.md`
- `plugins/drop_box/docs/drop-box.md`
- `plugins/drop_box/docs/drop-box-data-lifecycle.md`
- `src/orac_core/knowledge/managed_store.py`
- `src/orac_core/knowledge/retrieval.py`
- `src/orac_core/knowledge/materialisation.py`
- `src/orac_core/knowledge/materialisation_policy.py`
- `src/orac_core/knowledge/model_submission.py`
- `src/model/provider_registry.py`
- `src/model/orac_abc.py`
- `src/model/llm_connector.py`
- `src/orac_voice/voice_loop_local.py`
- `resources/config/orac.ini`
- `resources/db/schema/orac_core` and `resources/db/schema/orac_code`
- focused knowledge and connector tests named in the Phase 1 baseline.

### Database and provider evidence

- The 2026-08-22 SQLcl inventory was read-only and aggregate-only. It changed
  no database state and exposed no document content.
- Official provider pages are linked in the evidence-dated observations. They
  describe provider mechanisms, not current Orac capability.
- The configured local Ollama endpoint did not respond to a metadata-only
  model-list probe. P2-01 did not start a service, pull a model, load a model,
  or submit content.

### Gaps required for `VALIDATED`

For each proposed promotion, obtain an approved synthetic, openly licensed, or
otherwise redistributable fixture and record:

- owner, provenance, licence/approval, evidence date, and the user question;
- MIME signature, source bytes, container/member/page/sheet/slide/stream count;
- expanded/rendered bytes, dimensions and aggregate pixels, or decoded
  duration/frame/sample counts as applicable;
- derived-output bytes and provenance density;
- prohibited characteristics and expected rejection reason;
- evidence that deterministic Markdown/CSV/metadata alone cannot satisfy the
  outcome;
- local deterministic processor sufficiency;
- provider-class need, and, only where needed, separate provider-API and
  underlying-model verification.

No fixture was added merely to make this catalogue appear complete.

## Recommended input to P2-02

P2-02 should use this ordered evidence, without adopting the labels below as
final stable capability codes:

1. Deterministic source inspection and bounded selection are prerequisites for
   every candidate.
2. First-tier behaviours: PDF page inspection/rendering/OCR; selected-page and
   technical-image interpretation; spreadsheet parsing/calculation,
   sheet/chart rendering, and chart interpretation.
3. Second-tier behaviours: presentation extraction/rendering and selected
   slide interpretation; bounded local speech transcription with time-range
   provenance.
4. Deferred behaviours: cross-modal video interpretation and any direct Office
   container handling.
5. Cross-cutting requirements: source/derivative authority, selection
   granularity, provenance coordinates, local/remote eligibility, provisional
   media-specific ceilings, verified provider/model declarations, deterministic
   fallback, and content-free audit reason codes.

P2-02 must distinguish deterministic processors from optional specialist
models, and stable required behaviour from provider names, MIME labels, and
transport details. It must not treat the proposed ceilings as runtime
configuration or mark unverified backends as supported.

## Completion confirmation

P2-01 added this planning catalogue and documentation regression coverage only.
No runtime public interface, API, database object, privilege, configuration,
provider adapter, plugin capability, fixture in the live managed store,
managed-store mutation, model download, service change, binary ingestion,
multimodal materialisation, or attachment submission was introduced. Raw
binary remains unavailable in Phase 1, remote submission remains ineligible
without an approved sensitivity/locality policy, and final capability codes
remain deferred to P2-02.
