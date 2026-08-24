# Authorised Knowledge Retrieval

P1-06 adds a Core-internal, least-privilege boundary for reading document and
normalised artefact material. It does not add a public download endpoint or a
raw binary attachment route.

## Security boundary

The trusted Core host supplies the authenticated username, canonical scope,
and a caller-generated retrieval UUID. Oracle revalidates the active principal,
active and eligible scope, and current `USE` privilege inside
`orac_code.knowledge_retrieval_api` before resolving any target identity.
Unknown, inactive, expired, and ungranted cases all return the public
`RETRIEVAL_NOT_AUTHORISED` code, preventing target-existence probing.

Callers identify content only by document, document-version, extraction,
artefact, chunk-set, and chunk identities. Filesystem paths, Oracle directory
objects, `content_uri`, and managed-store keys are not accepted. The runtime
schema cannot read `knowledge_searchable_chunks_v` directly and cannot execute
the artefact registration package. Plugins, `ORAC_PLUGIN`, APEX, and
`ORAC_APX_PUB` receive no retrieval access.

## Supported retrievals

The version-1 request envelope supports authorised metadata and normalised
content for:

- the complete `PRIMARY` or spreadsheet `MANIFEST` representation;
- exact artefact identities or a contiguous artefact ordinal range;
- a half-open UTF-8 code-point range within one text artefact;
- contiguous chunk identities within one chunk set;
- a source section span anchored by the first and last contiguous chunks;
- an A1 cell rectangle contained by one registered `TABLE` artefact.

Document targets use the current document version. An exact historical version
identity may be requested. If a document version has more than one eligible
complete extraction, version-level content retrieval fails as ambiguous rather
than choosing by timestamp. Semantic heading-path selection belongs to P1-07.

Raw metadata may include registered hash, size, MIME type, original filename,
source format, and bounded extractor/artefact JSON. It never includes raw bytes
or locators. P1-06 content media are allowlisted UTF-8 Markdown, CSV, plain text,
and JSON. PDF, Office, image, audio, and other binary content is reserved for a
separate Phase 2 attachment route.

## Verification and limits

Before any managed content is returned, the service checks the registered size,
resolves the logical store identity under the fixed managed root, rejects unsafe
directory or file layouts, and verifies the complete source size and SHA-256 on
the opened descriptor. Selection occurs only after verification. Transformed
ranges receive their own emitted size and SHA-256.

The shipped hard ceilings are 256 metadata members, 32 selected members, 64
chunks, 10,000 table rows, 8 MiB per registered member, 16 MiB aggregate source
size, and 4 MiB emitted content. Output is never silently truncated. The
context-managed Python response yields at most 1 MiB per iteration block.
Oracle additionally limits one metadata JSON value to 64 Ki characters and the
aggregate metadata descriptors to 256 Ki characters before opening the result
cursor. Raw extractor metadata is selected only when explicitly requested.

Legacy extraction CLOBs remain readable when no artefacts exist. Their canonical
UTF-8 hash is verified against `text_sha256`, and results explicitly report a
null artefact identity and `LEGACY_EXTRACTION_CLOB` provenance. Before selecting
the CLOB, Oracle applies a conservative 2 Mi-character ceiling, which guarantees
an at-most 8 MiB UTF-8 source; the runtime then enforces the exact byte limit.
Chunk-range text receives an equivalent conservative aggregate character gate
before its cursor opens.

## Results and failures

Results contain the retrieval UUID, status, safe reason code, canonical scope,
controlled target identities, document/version/extraction provenance, member or
chunk identities and ranges, and source/emitted verification data. Workbook
results retain exact worksheet, table, source cell, header-row, hidden-sheet,
row, and chunk cell provenance whenever registered by P1-04.

Expected failures use stable `RETRIEVAL_*` reason codes for authorisation,
invalid or ambiguous targets, incomplete output sets, unsupported roles/media,
invalid ranges, exceeded limits, unavailable legacy content, unsafe/missing/
corrupt store objects, decoding, audit, cancellation, and internal failures.
Database errors, paths, content, and sensitive metadata are not copied into the
public reason.

## Audit and operations

Every decision is durably recorded before rows, metadata, CLOBs, or managed
descriptors become available. A terminal outcome records completed, failed, or
cancelled status, returned counts, the exact bytes actually yielded and their
hash, and duration. Audit rows
are append-only and retained indefinitely; P1-06 adds no purge operation.

Audit data excludes retrieved content, prompts, queries, filenames, worksheet
and table labels, metadata JSON, `content_uri`, storage keys, and physical paths.
Safe application logs correlate through retrieval UUID and reason code only.

If a privilege is revoked during an already approved bounded stream, that
stream may finish under decision-time snapshot semantics. Every new request
reauthorises. An audit decision failure prevents content from starting.

## Compatibility and extension

Existing RAG scoring, searchable/current-version filtering, candidate overflow,
grounding limits, and untrusted-evidence treatment remain unchanged, but the
chunk cursor is now opened by the authorised package. P1-04 artefact completeness
and provenance remain authoritative, and P1-05 records require no re-chunking or
re-embedding.

P1-07 consumes `KnowledgeMaterialisationService` through the progressive policy
documented in [Progressive Knowledge Materialisation Policy](knowledge-materialisation-policy.md).
It applies model/token budgets above these storage safety ceilings. Future binary attachment routing
must introduce a separate allowlisted capability and may reuse the identity,
store verification, provenance, and audit contracts without exposing paths.
