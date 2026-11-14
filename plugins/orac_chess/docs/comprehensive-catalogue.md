# Comprehensive source catalogue

The offline generator expands the existing Chess catalogue using the bundled,
CC0 Lichess opening dataset at revision
`3ba6b20d31b2e6125cb0e6a2e792f400717d9d39`. It verifies every source-file SHA-256
against the bundled provenance manifest and legally replays every source PGN
through `tools/mle/validator.mjs`, using the production `parse(pgn, 1)` policy.
It does not access the network or database.

Run from the repository root:

```bash
.venv/bin/python plugins/orac_chess/tools/generate_comprehensive_catalogue.py
.venv/bin/python plugins/orac_chess/tools/generate_comprehensive_catalogue.py --check
.venv/bin/python -m pytest tests/test_orac_chess_comprehensive_catalogue.py -q
```

Generated JSON is under `seed/catalogue/2026_11_10_comprehensive_catalogue/`.
It is deliberately separate from the released CSV batches discovered by the
legacy seed generator. The catalogue JSON is an offline proposed payload;
its presence does not install or refresh database records. Runtime incremental
synchronisation requires the separately reviewed reconciliation mechanism.

## Mapping and identity

`seed/mappings/lichess_families.json` explicitly maps all 149 source top labels.
The generator reads that mapping; it does not infer families by splitting names
at arbitrary commas. Accepted/declined labels normally map to the underlying
family, while the established Queen's Gambit Accepted and Queen's Gambit Declined
opening identities remain separate. Explicit source comma forms map to their
reviewed family. Nimzo-Larsen Attack retains the existing Larsen's Opening
identity and alias. Lion Defense retains the existing Black Lion alias. The
source B00 Lion's Jaw line lacks sufficient compatible Black Lion root moves;
it is explicitly deferred and contributes neither a branch nor an ECO link.

All 50 existing openings and 40 existing gambits retain their names, types,
descriptions, parents and representative PGNs. Their 90 mainlines and 100 named
branches remain in released batches. Existing video relationships are outside
this transformation. New source-recognised systems use the `SYSTEM` type.

A gambit candidate must be a complete source naming segment ending in `Gambit`
or `Countergambit`, optionally followed by `Accepted` or `Declined`. The source
syntax separates the top family with a colon and named descendants with commas.
This recognises source terminology rather than searching arbitrary substrings.
Reviewed synonym overrides are declarative. Existing named attacks remain
curated gambits. A source gambit carries every opening context in which it is
observed. Queen's Gambit is one shared gambit across its accepted/declined
opening classifications. Repeated eponyms in different families, including Wing,
Zilbermints and Marshall, receive context-qualified names unless an explicit
shared-concept override documents that they are one gambit. Original curated
names retain their established source context.

For each owner and source-named concept, the canonical representative is the
shortest legal source sequence, with normalised UCI history as tie-breaker.
This is a deterministic reference line, not a popularity claim. Every other
occurrence and its move history remains in `coverage.json`. Distinct named
concepts are retained even when their final positions coincide. Equal UCI
histories and equal final positions are reported separately; this pinned source
currently has no duplicate final positions under the normalised four-field FEN
comparison.

Initial source keys hash owner type, canonical owner, source concept and
normalised UCI history. `SOURCE_IDENTITIES.json` freezes those released keys.
The generator reads that frozen registry and reuses its released key when the
same owner/context and source concept receive corrected moves. The new content
hash changes while the initial move-derived identity remains fixed. A renamed
source concept requires an explicit new-derived-key to released-key entry in
`source_key_overrides`; do not silently replace released identities.

Owner IDs additionally bind `(owner type, canonical owner name)` to the previous
released `catalogue.json`. A newly selected shorter source representative with a
different source concept therefore retains its owner ID and its derived MAIN ID.
If the old representative becomes a newly stored branch, it receives a distinct
branch identity instead of reusing the owner identity from its original source
occurrence; subsequent corrections reuse that frozen branch identity.
A reviewed new release can use separate source, mapping and output locations:

```bash
.venv/bin/python plugins/orac_chess/tools/generate_comprehensive_catalogue.py \
  --source plugins/orac_chess/vendor/NEW_PINNED_SOURCE \
  --mapping plugins/orac_chess/seed/mappings/NEW_REVIEWED_MAPPING.json \
  --output plugins/orac_chess/seed/catalogue/NEW_RELEASE \
  --previous-catalogue plugins/orac_chess/seed/catalogue/2026_11_10_comprehensive_catalogue/catalogue.json \
  --identities plugins/orac_chess/seed/catalogue/2026_11_10_comprehensive_catalogue/SOURCE_IDENTITIES.json
```

The new source still requires a complete pinned-file SHA-256 provenance manifest.
Use an explicit reviewed alias/key override for source renames or changed canonical
owners; the upstream dataset provides no persistent IDs for automatic rename
inference. Existing catalogue inputs require the released identity registry.

Each proposed record also has a SHA-256 source
content hash. Relationship keys and provenance are separate from owner records.
These are inputs to reconciliation, not permission to overwrite existing rows.

## Hierarchy and omissions

A named ancestor is considered only within the same owner and when the source
child name extends its named parent. Its legal sequence must be a strict prefix
of the child. The nearest such source-named ancestor is used. No artificial
two-level limit is imposed. Otherwise the owner mainline is used when compatible.
`CONTINUATION` means the child contains every parent UCI move followed by at least
one move, with `branch_ply` equal to the parent move count. `ALTERNATIVE` means
actual divergence before the parent ends, at the exact common-prefix ply.

A short source line that is a strict prefix of a preserved long mainline cannot
be represented as either edge. It remains a reported omission; the generator
does not rewrite the curated root. Bare opening-family rows are represented by
the family owner. Existing branches and owner-mainline sequences are reported
as already represented. All 3,865 source rows remain accounted for through
source occurrence provenance and the explicit deferred-row report, including
alternate occurrences of a named concept.

Descriptions and annotations for new records state the recognised source name
and actual moves. They contain no generated strategic chess claims.

## Coverage and verification

`coverage.json` contains actual counts, opening/source breakdown, ECO A–E group
breakdown, every opening/ECO association, unassigned codes, omission reasons,
source occurrences, duplicate histories, transpositions and explicit mapping
ambiguities. The source supports all 500 ECO codes; no associations are invented
to fill gaps. Existing direct mainline/gambit ECO fields remain compatible with
the central opening/ECO mapping.

The offline tests verify source hashes and legal replay, deterministic bytes,
curated-field preservation, mandatory entries, alias uniqueness, context-qualified
gambits, ownership, cycles, orphan prevention and exact hierarchy move semantics.
Database fresh-install, rerun, user-edit preservation, upgrade and video-link
acceptance are separate checks and are not certified by offline generation.

The current generated payload contains 128 openings/systems, 612 gambits and
3,718 new named branches and 650 new owner mainlines: 4,368 new variation
records in total. The 190 existing records comprise 90 owner mainlines and
100 curated named branches. Those 100 prior branches are absent from the sync
payload and remain protected, untracked existing data. The payload references
4,458 variation records (740 owner mainlines plus 3,718 new branches), giving
a projected installed total of 4,558 including the 100 prior branches.
There are 614 opening/gambit relationships and 3,818 parent-child edges overall
(3,718 new plus 100 prior). Of the new edges, 1,595 use another named branch
as their parent; this is the nested named-branch count, not all parent-child edges.
All 3,865 source PGNs are legal: 3,864 rows map confidently and one Lion's Jaw
row is deferred. All 500 ECO codes have evidenced source opening associations.
The payload contains more gambits than the indicative request because the source
recognises many historically named gambit branches; no arbitrary count limit is
applied. Context qualifiers distinguish repeated eponyms rather than merging
unsupported identities.

Source accounting distinguishes import omissions from existing representations.
There are 43 named-branch omissions because their source sequences are strict
prefixes of preserved long mainlines, plus one unresolved Lion's Jaw source row.
The 63 family contexts, 719 owner-mainline contexts and 94 prior-variation
contexts are already represented; they are not rejected source data. Counts of
these contexts must not be subtracted as mutually exclusive raw source rows.
Repeated display names occur in 308 groups containing 996 source rows: 688
additional occurrences beyond each group's first row. Those occurrences are
coalesced per owner/context/concept using the documented canonical representative
and retained individually in provenance. They are not 688 illegal sequences.

## Original strategy release

The additive `2026_11_12_strategy_catalogue` release retains the preceding
catalogue's stable keys, identities, names, descriptions, moves and relationships.
The versioned overlay `seed/strategy/2026_11_12/strategies.json` records original
Codex-assisted prose, exact reference PGN/FEN and source SHA-256. Each of 128
opening/system and 612 gambit records has an 80–130 word strategy. Plans apply
to the supplied reference position; a representative branch does not define
every member of a broad opening family. No engine evaluation is claimed.

Regenerate or check with `python3 plugins/orac_chess/tools/generate_strategy_catalogue.py --check`.
The historical generator's default release identifier, date and bytes remain
unchanged. Strategy is optional desired state: absent leaves it untouched,
explicit null clears it. A blank new field can be initialised when no baseline
or explicit override exists, including on adopted records. Subsequent edits and
clears are retained by normal three-way merge. Nonblank pre-existing strategies
remain user-owned on adoption. Content and baselines survive release rollback;
use a forward correction rather than destructive rollback.

## Editorial strategy release

The additive `2026_11_13_editorial_catalogue` release preserves all 740 owner
identities, reference PGNs/FENs, names, non-strategy fields and equivalent-position
metadata. Its overlay is `seed/strategy/2026_11_13/strategies.json`. The preceding
12-Nov release remains immutable and reproducible with the same generator.

This bounded revision retains the original position-specific reasoning. It
replaces 234 speculative bishop sentences with verified diagonal facts and 234
categorical f-pawn shelter claims with cautious development and king-safety
wording. It makes 375 pawn-break suggestions conditional on legality and tactics.
For the Tal Gambit (Petrov), it explicitly rejects d7–d6 while the d7-pawn is
pinned to e8 by the bishop on b5. It repairs 116 coordinate lists and six missing
sentence separators, and corrects 33 singular-pawn references. These checks
establish board facts, not engine evaluations
or the soundness of every strategic recommendation.

All narratives now have topical blank-line paragraphs: the two sides' plans,
break timing and calculation, then supporting positional facts where present.
Kholmov Gambit needs only the first two paragraphs. No word minimum was imposed
on the editorial revision. Descriptions and commentary were unchanged in the
supplied archive and remain unchanged here. The archive's broader replacement
prose was excluded because it discarded useful specifics and repeated identical
narratives across different reference positions.

The generator command above now writes/checks both strategy releases. The new
catalogue passes through the existing normalisation and private sync API; source
hashes in the normalised payload are recalculated rather than substituted into
historical catalogue fields. Controller `15_eco_seed_batches.xml` applies this
once-only batch after the original strategy batch. Existing three-way merge and
rollback handling remain in force; user overrides are not authorised for replacement.

Offline tests replay PGNs, check cited bishop rays and pawn-break board geometry,
protect the Tal pin correction, and decode the SQL payload to verify paragraph
round trips. `db/acceptance/verify_strategy.sql` additionally exercises multiline
source updates, reruns and local overrides against installed APIs with rollback.
Live fresh-install, upgrade and acceptance execution still require a separately
authorised database run. Existing APEX textareas and the escaped CLOB gambit drawer
preserve newlines; query-table cells collapse whitespace, so paragraph layout is
not asserted for those cells. No APEX change is included.
