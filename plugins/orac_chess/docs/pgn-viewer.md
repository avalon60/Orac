# PGN move viewer

The Orac Chess Explorer application (`10030`, alias `ORAC_CHESS_ADMIN`,
workspace `ORAC`, parsing schema `ORAC_APX_PUB`) includes a read-only browser move
viewer. Opening page 11, Gambit page 21 and the Gambit Details drawer on page 22
show the subject's principal lines and child variations. On Opening, Gambit and Variation pages, select **PGN Viewer** in the region display
selector to see the board in its own region selection. Gambit also groups
Synopsis, Variations and Linked openings, with related videos remaining visible.
The read-only Gambit Details drawer has its own titled viewer region. The Variation drawer opens on **PGN Viewer**; its **View** selector also offers **Variation details** and **ECO Codes**, each with a dedicated display. The Opening includes
lines belonging to its linked gambits. Existing maintenance controls, ECO
links and disclosures remain alongside the viewer. Variation drawer 31 previews
the current unsaved PGN; **Update preview** reads the current editor values.
The Variation preview has no line selector, pagination or principal-line action.
It reads the editor PGN and starting FEN, using the parent's root FEN when a parent
is selected; it does not load stored explorer lines or save edits.
Saving remains the existing form action.

Choose a line, then use **First**, **Previous**, **Next**, **Last**, or select a
move directly. **Flip** changes the board orientation; **Reset** restores the
initial position and White orientation. With focus inside the viewer, Left and
Right navigate; Home and End select the first and last position. Editing a PGN
textarea does not trigger those shortcuts. The move list and board mark the
current move. No autoplay, move input, engine, analysis or evaluation is supplied.

On pages 11, 21 and 22, principal and child lines are grouped in the selector. Child labels distinguish
an alternative from a continuation and give its branch half-move count. Each
stored child PGN is already a complete line from the root position: the viewer
never appends it to its parent. Before displaying a child, the browser checks
its complete parent prefix and branch point using the catalogue's strict policy.
It starts at the branch position; **Return to principal line** selects the root.
A contradictory relationship is unavailable with an explanatory message. Missing
and invalid PGNs clear the previous board and disable move navigation.

## Browser contract

`browser/model.mjs` builds SAN/UCI moves and an initial plus one six-field FEN
snapshot per half-move using pinned `chess.js` 1.4.0 (BSD-2-Clause). It reuses
`tools/mle/validator.mjs` without modifying that policy. Complete single-game,
linear PGN is required, including a terminal result (`*` is suitable for an
instructional line). Comments, move numbers, NAGs and SAN annotation suffixes
are supported. Recursive annotation variations, multiple games, malformed,
trailing or incomplete input are rejected explicitly. FEN games require paired
`SetUp "1"` and `FEN` headers matching the effective root's starting FEN.
An absent starting FEN uses the normal initial chess position.

`browser/viewer.mjs` exports `PgnViewer`:

```javascript
import {PgnViewer} from './viewer.mjs';
const viewer = new PgnViewer({container: document.querySelector('#board')});
viewer.loadPgn('1. e4 e5 2. Nf3 Nc6 *');
viewer.goToMove(3); // half-move count: 0 is the initial position
viewer.previous();
viewer.flip();
viewer.reset();
viewer.destroy(); // idempotent
```

The other navigation methods are `first()`, `next()` and `last()`.
`loadPgn(pgn, startingFen = null)` returns success as a boolean. Loading failure
clears old positions. Navigation clamps to the available range. Each instance
owns its game, board, controls and event listeners. Destroy releases the board's
resize observers and removes the instance DOM. Import `viewer.css` for layout.
Treat a destroyed viewer as disposed and construct a new instance for remounts.

The SVG renderer is `cm-chessboard` 8.15.4, MIT code. Both upstream piece sets
are excluded: `standard.svg` is CC BY-SA 3.0 and `staunty.svg` is CC BY-NC-SA 4.0.
The viewer uses original, conventional geometric piece silhouettes in
`browser/pieces.svg`, licensed separately under MIT in `browser/PIECES-LICENSE`.
The retained upstream files are byte-for-byte from the pinned npm tarball;
`vendor/cm-chessboard-8.15.4/PROVENANCE.json`, `LICENSE` and `SHA256SUMS` record
source, exclusions and checksums. No CDN, network chess service, engine, Python
chess package or new database chess object is used for replay.

## APEX delivery and maintenance

`browser/apex.mjs` owns page adapter instances, bounded metadata pagination
(100 displayed rows per request) and selected full-PGN retrieval. Page-local
`PGN_VIEWER` callbacks read only approved `chess_variation_v` and related views.
Numeric identities are checked and selected lines are constrained to the active
subject. Metadata does not fetch PGN CLOBs. Selected PGNs use `apex_json.write`
with the CLOB overload, without truncation. Only a selected child and its parent
are fetched to verify a relationship. Root starting FEN is resolved through the
existing parent hierarchy. Existing application and page authentication and
authorisation remain unchanged; this feature adds no role restriction or grant.

The adapter ignores stale responses, aborts outstanding requests when disposed,
and destroys boards before region refresh or after dialog DOM removal.
`bootstrap.mjs` mounts after page/region rendering; renderer ResizeObserver support
handles visibility and width changes. PGN, names and errors are rendered with
`textContent`; supplied content never becomes executable HTML.

Regenerate the marked PGN sections in the existing export, then the recovery
export. This keeps existing ECO generation independent:

```bash
python3 plugins/orac_chess/tools/generate_viewer_apex.py
python3 plugins/orac_chess/tools/generate_mle_recovery.py
python3 plugins/orac_chess/tools/generate_viewer_apex.py --check
python3 plugins/orac_chess/tools/generate_eco_apex.py --check
python3 plugins/orac_chess/tools/generate_mle_recovery.py --check
node plugins/orac_chess/browser/model.test.mjs
node plugins/orac_chess/browser/viewer.test.mjs
node plugins/orac_chess/browser/apex.test.mjs
.venv/bin/python -m pytest -q tests/test_orac_chess_pgn_viewer.py
```

The generator maps browser modules, reused policy, legal-move library and renderer
resources to content-addressed `pgn/<hash>/` application static files, preserving relative imports and
byte-identical resource contents. The content hash changes whenever a shipped
resource changes, including every relative module import URL, preventing stale
browser code after repeated APEX imports. Hand edits belong in browser sources and the
generator, not the generated sections. Variation31 and Video41 use the same slide-out drawer page template as Gambit
Details22. Save, Cancel and platform close-dialog/refresh actions retain their
existing behaviour; inline ECO editors and Popup LOV widgets keep their native
interaction. The existing host installer imports the
application and reconciles its receipt. An APEX-only update is sufficient for
this feature; no schema migration is needed.

For an offline fixture, serve the repository with `python3 -m http.server 8766`
and open `/plugins/orac_chess/browser/fixture.html`. It provides two independent
viewers, PGN editing, invalid/empty states and repeated disposal/remounting.
Serve over HTTP so the browser can load ES modules and SVG sprites. The fixture
contains no external requests. Catalogue examples must be checked against the
installed catalogue rather than inferred from their display names.

Opening and Gambit details open with PGN Viewer selected. The saved subject name
and direct ECO descriptions remain visible above View. Synopsis follows PGN Viewer
and precedes Variations. The paginated read-only Variations report lists relevant
lines without loading PGN text. Opening includes variations of linked gambits.

Opening View also offers **Aliases** and **Gambits**, each showing its existing
report and association controls only while selected.

On Opening, select a name in **Variations** to open the existing Variation
slide-out drawer. The selected line uses its protected variation ID; the
Gambit Variations report continues to show plain names.
