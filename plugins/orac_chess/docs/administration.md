# Orac Chess Administration

The plugin owns the data and all maintenance APIs in `ORAC_CHESS`. Its APEX
application uses workspace `ORAC`, parsing schema `ORAC_APX_PUB`, Universal Theme,
and the stable alias `ORAC_CHESS_ADMIN`. The manifest explicitly assigns app ID
`10030`; the host records its installation receipt. Former app `100` was removed
on 08-Nov-2026. Never import into an unrelated application ID.

## Pages

| Pages | Collection | Details |
| --- | --- | --- |
| 1 | Home | Collection navigation |
| 10 / 11 | Openings and systems | Classification, parent, aliases, ECO and gambit links |
| 20 / 21 | Gambits | Name, description and multiple linked openings |
| 30 / 31 | Variations | Owner, parent, complete linear PGN and root FEN |
| 40 / 41 | Videos | Metadata, HTTP(S) URL and subject links |
| 50 / 51 | Concepts | Code, category and subject links |
| 60 / 61 | Games | Complete PGN and separate searchable metadata |
| 70 / 71 | Commentary | Exactly one opening, gambit or variation |
| 80 / 81 | Images | Metadata, explicit upload replacement and subject links |
| 90 | Image delivery | Authenticated, authorized content only |
| 110 / 111 | Content Sources | Creator / publisher, author and notes |
| 9999 | Login | Existing Oracle APEX Accounts |

The Opening detail page uses **View** to switch between **Opening Synopsis**,
**ECO Codes** and **Opening Gambit**. Opening Synopsis is selected when the
page opens; the selector does not remember the previous selection.

On the Variations collection page, use the native region display selector to
choose **Report** or **Variations Hierarchy**. Report is ordered first and the
selector does not remember the previous selection, so the interactive report is
the intended default when opening the page. Hierarchy links open the existing
Variation detail dialog.

Collection pages use interactive reports. In the Videos report, clicking a video
title opens its video URL in a new tab. Associations are edited inside detail
pages, rather than exposed as top-level collections. Cancel navigates away without
submitting. Save and delete carry observed `row_version` values; stale versions are rejected.
Opening and Gambit version items permit exact versions returned by video actions
to be applied in the browser; protected subject identities and API version checks
remain authoritative. Deletes are restrictive, except controlled image deletion which
removes image associations in its own savepoint. Unlinking never deletes shared
material.

Video Platform is a static select list, initially containing and defaulting to
YouTube. Existing platform values remain visible when editing older records.
The Videos report opens Video URL links in a new browser tab.

Opening and Gambit detail pages have a **Related videos** region. Each linked
video shows its title, creator and formatted duration, with **Watch** opening its
HTTP(S) URL in a safe new tab. **Edit video** opens the shared Video modal.
**Unlink** asks for confirmation and removes only that subject's association;
the shared video and its other associations remain. Expand **Link existing
video** to search titles, creators and platforms; already linked videos are
excluded. Click **Link** beside the chosen video to add it immediately; entering
a search alone does not add an association. Save a new subject before adding
videos. Wait for a video action to finish before saving the subject. The page
blocks submission while the action is pending so Save uses its returned version.

**Create video** opens a cleared Video modal. Saving from a subject creates the
video and its association atomically; a stale or invalid subject leaves no new
video behind. Creating from the main Videos page creates an unassociated video.
Cancel closes the modal without submitting or validating. Invalid input keeps
the modal and its origin context available for correction. Saving closes it and
refreshes the originating video region while preserving unsaved subject fields.
Metadata-only video edits do not advance the subject's observed version. Link
mutations return exact versions and the parent adopts them only for the same
subject, observed version and client correlation token; another tab or stale
response cannot silently replace that token. Refreshing the video list never
fetches a newer subject version. A stale action requires reloading the subject.

The Video association reports display subject names. A reciprocal link closes
the Video modal before the parent navigates to the selected Opening or Gambit,
or opens the selected Variation. Existing Video association controls remain
available. Mutations affecting the originating Opening/Gambit also check its
observed version.

Use **Content Sources** to maintain the creator or publisher name, author and
optional notes. Videos share these sources. The Video **Creator** popup shows
creator / publisher and author in separate columns and searches both; selecting a
row stores its exact creator name. Leave Creator blank when no source applies.
Create a source before assigning it to a video. A source used by a video cannot
be renamed or deleted; its author and notes remain editable. An unused source
can be renamed. Cancel leaves the saved source unchanged.
Video URL appears before External Video Id. When URL or Platform changes and
Platform is YouTube, a recognised URL fills the editable External Video Id:
`youtube.com` (also `www` and `m`) supports `/watch?v=ID`, `/shorts/ID` and
`/embed/ID`; `youtu.be` (also `www`) supports `/ID`. HTTP and HTTPS URLs are
accepted, including timestamp and other query parameters. IDs must contain
exactly 11 letters, digits, underscores or hyphens; duplicate `v` parameters
on watch URLs are rejected. This recognises URL shapes without checking whether
a video exists or fetching it. A valid changed URL replaces the current ID;
unsupported or invalid URLs and other platforms preserve it. Opening a record
does not default the ID, and it remains manually editable.

## API and grants

Public definer-rights packages are `chess_admin_api` (reference entities and
explicit associations), `chess_variation_api`, `chess_game_api` and
`chess_image_api`. Specifications under `db/schema/package_spec` are the exact
scalar contracts. `p_id` is null for insert; updates/deletes require the observed
version; saves return the new version. Every composite operation rolls its own
work back on failure. The caller alone commits or rolls back the transaction.

`chess_admin_tapi` and `chess_validation_api` are private. Only SELECT on explicit
`chess_*_v` read views and EXECUTE on the four public packages are granted to
`ORAC_APX_PUB`. No base DML, private API, PUBLIC grants or public synonyms are
introduced. Image listing views contain byte length and metadata without BLOBs.

The singleton `chess_admin_control` serializes maintenance operations before
hierarchy checks, preventing concurrent write-skew cycles. Row locks and stale
version checks occur after that lock. Association edits increment the subject
and shared material aggregate versions. This intentionally favors correct,
low-volume administration over concurrent write throughput.

## PGN validation

The active deployment chain loads unchanged, pinned MIT-licensed chess.js 1.4.0,
the policy already exercised by the isolated Oracle proof, and a separate typed
production CLOB bridge. `chess_mle_lib`, `chess_mle_policy`, `chess_mle_bridge`,
`chess_mle_env`, and the three `chess_mle_*` call specifications are private.
The environment is PURE; no SQL, network, filesystem or external service is
used by the validator. The host provisions CREATE MLE only for the exact
`orac_chess` / `ORAC_CHESS` pair, in addition to its existing owner grants.
No consumer MLE or private API grant is introduced.

`tools/generate_mle_runtime.py --check` verifies source reproducibility and the
upstream pin. Generated module loading uses UTF-8 hex CLOB chunks so SQLcl
cannot rewrite JavaScript escapes. Each module, environment and call specification
has its own replaceable changeset before the public API controller. The final
compile pass rejects invalid objects and executes a legal-PGN semantic smoke.
The 161 baseline changesets and historical diagnostic history are preserved.

Validation consumes every token, checks canonical SAN against legal library
moves, replays every game RAV, and verifies FEN/SetUp and result consistency.
Variations accept one complete mainline with comments/NAG and reject RAV.
PGN is bounded at 4 Mi characters (also checked against JavaScript UTF-16 length),
and RAV depth at 64. Original PGN text and annotations remain unchanged.
Runtime exceptions fail closed with `-20020`; invalid PGN uses `-20021` and
invalid branch relationships use `-20025`. Public save operations use the existing
private TAPI savepoint, locks and optimistic version checks.

A root uses `MAIN`. An `ALTERNATIVE` child stores the complete line, with the
same root initial position and normalised prefix through `branch_ply` shared
half-moves. Both lines need a next half-move and those moves must differ;
identical lines and pure extensions remain invalid alternatives.

A `CONTINUATION` child instead extends its complete parent by at least one legal
move. Its `branch_ply` equals the parent's half-move count, and every parent UCI
move and intermediate position must match the child's prefix. Equal, shorter or
different-prefix lines are rejected. This additive line kind does not change
`MAIN` or `ALTERNATIVE` semantics or public writer signatures.

Both child kinds inherit the same owner and root initial position. Child FEN is
null; a nonstandard root FEN must appear in every PGN with matching SetUp `1`.
Existing-node updates use whole-tree validation to resolve the true root, reject
cycles/rootless ancestry and validate every descendant according to its own line
kind. New inserts still validate the complete PGN, immediate parent edge, owner,
cycle prevention and inherited root FEN under the aggregate lock. The newly
allocated primary key cannot already have descendants under the immediate
composite parent foreign keys, so inserting that leaf does not rescan unchanged
siblings. Updates retain full descendant validation. Parent changes
that invalidate any retained descendant roll back atomically. Ordinary variation
maintenance cannot change ownership. Runtime withdrawal fails both edge kinds
closed. The structural migration widens the check before retiring the old narrow
check; rollback retains additive support so valid continuation data is not
stranded. No production tree-depth limit is introduced. The original curated CSV
batch's two-edge packaging rule remains unchanged.

Variation owner and parent choices use native searchable popup LOVs with the
first server-fetched rowset, rather than rendering every catalogue record as a
select option. Parent choices are scoped to the selected opening or gambit,
exclude the edited variation, and show line kind. Owner changes refresh the
parent choices; existing variation ownership remains read-only. Backend cycle,
owner and complete-move validation remains authoritative. Recovery displays the
three fields as read-only values.

Pages 30/31 and 60/61 provide create, edit, save, cancel and conditional,
confirmation-protected delete. Variation edits use the existing modal, close it
after success and refresh the collection. Game edits remain a full page. Subject
type selects the visible owner selector; existing variation ownership is read-only
and enforced again by the server. The game's **Fill empty fields from PGN** action
validates complete PGN and fills only empty White, Black, Event, Site, Result and
ECO metadata. It never saves or overwrites populated fields. All Chess application dates use DD-Mon-YYYY with English month names (for example
07-Nov-2026), including published dates, game dates and reports. Video duration
accepts MM:SS or HH:MM:SS, such as 09:30 or 1:02:30, and is stored as whole
seconds. Blank duration remains optional; zero, malformed values and values above
9999999999 seconds are rejected on Save. Report durations use the same readable
format while sorting and filtering use numeric seconds. The internal page item
P41_DURATION_SECONDS retains its name but now carries the formatted text; the
Save process converts and validates it before calling the unchanged numeric API. Runtime browser verification remains outstanding.

The Java source candidate, source-DDL parser failure (ORA-29536), and cleanup
record remain under diagnostics and [verification](verification.md). They are not
included in production deployment.

### Recovery

`tools/generate_mle_recovery.py --check` verifies a data-preserving withdrawal
bundle. First use the host receipt/import path to import
`apex/recovery/orac_chess_admin_readonly.sql`, preserving installed application 10030.
Then an explicitly approved owner/admin may execute
`db/recovery/mle/withdraw.sql`: restore fail-closed writer and validation bodies,
verify compilation, then remove the seven private MLE objects in dependency order.
It preserves tables, data, Liquibase history and existing privileges. Do not run
normal forward deployment until deliberately reapplying the integration; its canonical runtime objects and affected facade/writer bodies use runAlways
as well as runOnChange. This deliberately recreates withdrawn objects and restores
writers through the ordinary managed route without clearing history/checksums.
The approved DEV withdrawal and ordinary managed reapplication passed on
07-Nov-2026; see the [verification record](verification.md).

## Images and URLs

Image alt text is required. Uploads accept PNG/JPEG only, with server-side signature, chunk/segment structure
and size validation. PNG chunks require CRCs, legal IHDR, ordering and IEND;
JPEG requires supported frame, valid quantization/Huffman tables, matching scan
components, bounded segments/scans and a final EOI. Both are
limited to 16 megapixels. This is bounded structure validation, not pixel-level
PNG deflate/JPEG entropy decoding; that remains an explicit validation limit. Metadata-only saves pass a null replacement BLOB and retain
bytes and MIME. Replacements supply a new BLOB and MIME together. The default
persisted upload limit is 10 MiB. An authorized DBA can change it separately:

```sql
update orac_chess.chess_admin_control
set max_image_bytes = 10485760 where control_id = 1;
commit;
```

The positive integer check prevents disabling the limit. This operation is
administrative configuration and is not an APEX parsing-schema privilege.
Image delivery sends an allowlisted MIME, sanitized inline filename,
`X-Content-Type-Options: nosniff`, and private/no-store cache policy. Page 90
uses the same authentication and authorization as every maintenance page.
Video/source URLs accept HTTP(S), reject controls and markup, and are never
fetched. Video ingestion, transcripts, YouTube APIs, MCP, AI and engines are
outside this application.

## Authentication and deployment

Every protected page applies both
`plugin_apex_app_auth_api.plugin_is_available('orac_chess', :APP_ID)` and
`has_required_role('ORAC_ADMIN')`, with NOCACHE authorization evaluation. The
application uses existing workspace accounts; deployment creates no credentials.
Host cross-app navigation is retained. Disabling the plugin denies the app and
image delivery.

Deploy only through the existing host lifecycle:

```text
bin/orac-plugin.sh install --bundled orac_chess
bin/orac-plugin.sh check orac_chess
```

The production controller has additive administration migrations after the
unchanged 161-changeset baseline. It installs structural additions, technical
comments/annotations, views, package specs/bodies, consumer grants and a final
dependency-order body compilation pass. Reference data `13` precedes baseline
APIs `10`, then final ECO contracts and their compile check `14` precede shared
compilation `11`, bootstrap seeds `12` and ECO seeds `15`. This order prevents an
unchanged ECO body being compiled against the temporary baseline specification.
Controller `15` is included once at the root. The compilation pass prevents
unchanged bodies remaining invalid after a specification upgrade. The failed Java chain is excluded. Do not reset
checksums, rewrite baseline scripts, or remove/recreate the schema for upgrades.
The manifest preserves the existing disabled default. The host owns live
registration enablement and receipt reconciliation.

The canonical application asset is `apex/orac_chess_admin.sql`. After an
intentional Builder change, export the verified installed app through SQLcl,
replace this asset, and preserve the alias, parsing schema, required receipt
setting, plugin/role checks and host return navigation. Reset the exported
`ORAC_INSTALL_RECEIPT` value to `UNATTESTED`; the host reattests it during import.
Keep the standard display-name prologue because the host initially sets the name
to the alias. Reinstall twice to verify receipt
identity and repeatability. Keep optional Chess dependencies out of core install.

## Verification

Run the local authoritative validator corpus:

```text
.venv/bin/python -m pytest tests/test_orac_chess_validator.py
python3 plugins/orac_chess/tools/generate_java_sources.py --check
```

Database verification must also exercise the public APIs, invalid input,
optimistic versions, association rollback, hierarchy cycles, parent subtree
revalidation, image content and parsing-schema denials. Roll back disposable
fixtures. Run two-session concurrency checks and install/upgrade repeatability.
Authenticated browser smoke requires an existing authorized workspace account;
metadata checks alone do not prove runtime usability.

utPLSQL is a separate development prerequisite, never bundled by this plugin.
No LOGGER instrumentation is introduced, as requested. See the
[verification record](verification.md) for actual results and remaining limitations.

To generate data-preserving Oracle acceptance checks for these conversions, run
`python3 plugins/orac_chess/tools/generate_duration_date_acceptance.py --output /tmp/chess_duration_date_acceptance.sql`.
Run the generated script in a disposable SQLcl session against the approved DEV
database. It extracts the actual APEX conversion code, checks valid and rejected
durations, numeric round trips and English dates under a French session language.
It performs no application data writes and restores English session language.
This check complements the authenticated form and report browser checks.

## ECO assignments

Openings, gambits and variations each have their own direct ECO assignments.
Use **Edit ECO Codes** to search by code or any part of the complete description.
The dialog's Save stages a complete selection, including an empty selection; the
form's Save applies it. Dialog Cancel leaves the staged selection unchanged, and
form Cancel discards the staged changes. A normal form save preserves ECO codes
when the editor was not saved. The collection reports filter the direct codes
shown for each row. A game has its own optional ECO code, independent of its
linked opening; no classifier runs automatically.

A variation's **Related ECO Codes** shows codes assigned to ancestor variations
and its owning opening or gambit. A gambit's related codes come from explicitly
linked openings. Related entries identify their source and are context only; they
do not assign those codes to the current record. Expand a code to read its full
reference description. The same description is used across all three collections.

The ECO extension is installed after the existing administration and seed
controllers. Opening and game assignments must already refer to the complete
catalogue, or its preflight halts for investigation. The new gambit and variation
mappings start empty. A populated mapping is not automatically dropped on
rollback; retain the data and repair the installation forward. Do not edit
historical changesets, reset checksums, or change the APEX identity or receipt as
part of recovery.

For future CSV seed batches, `gambits.csv` may add `eco_codes`, and either
`openings.csv` or `gambits.csv` may add `mainline_eco_codes` for the created
mainline variation. Values are pipe-separated, for example `C25|C29`.
Mainline codes require a mainline PGN. These optional assignments are applied
only when the corresponding gambit or variation is created; existing records and
their codes are preserved. ECO-aware batches are generated with the later runtime
and registered after the extension APIs. Existing released batches and their
generated SQL remain unchanged.

The additive DEV upgrade, repeat install and APEX source import were checked as
described in [the verification record](verification.md). Browser interaction,
accessibility and fresh or isolated populated installation remain unverified.

### Isolated acceptance procedure

In an isolated disposable database, install the plugin from an empty schema and
run `db/acceptance/verify_eco_reference.sql` and
`db/acceptance/verify_eco_assignments.sql`. Repeat from a populated pre-extension
installation with saved opening and game assignments and an edited catalogue
description. Capture the Liquibase history and checksums, catalogue descriptions,
assignments, app ID and import receipt before upgrading; compare them after the
upgrade and after repeating it. Confirm no existing values were rewritten, all
objects are valid, and APEX retains only the intended reads and public API grants.
A preflight mismatch must halt without advancing the ECO extension.

In an authenticated browser, test all three forms with an existing record and a
new record. Save a multi-code selection, reopen and filter it, and confirm choices
survive searching and pagination. Open and cancel the editor, clear its selection
and cancel the main form, then clear it again and save the main form. Check that
ordinary saves, missing or stale editor values and switching records do not clear
assignments. Exercise stale versions and invalid selections, and compare direct
filters with labelled related context. Check keyboard operation, narrow screens,
long Unicode descriptions and searches beyond the preview. For example, Vienna
has a C25–C29 family, while a specific line may use C29; individual gambits can
have C25, so do not infer a code from a name. These checks require an approved
isolated environment and have not been run as part of the source change.

`python3 plugins/orac_chess/tools/generate_eco_apex.py --check` verifies that the
marked editor and disclosure components match their shared templates. After a
source change, regenerate those fragments and then regenerate the read-only
recovery export with `tools/generate_mle_recovery.py`.

## Strategy

Opening page 11 and Gambit page 21 have a separate **Strategy** textarea after
Description. Save writes the full strategy; clearing the field explicitly clears
it. Description retains its existing concise reference purpose. Legacy API
callers retain their signatures and preserve strategy on update. New overloads
accept `p_strategy` immediately after `p_description`; explicit null clears.
All operations retain optimistic locking and the caller-owned transaction.

### Gambits linked to an opening

On an Opening, select **Opening Gambit** to see each linked gambit's name and a
short description (up to 240 characters). Internal identifiers are hidden. Select
a gambit name to open the read-only **Gambit Details** drawer with its full
Description and Strategy. **Close** returns to the same opening without saving
or submitting its form. Missing descriptions and strategies have explanatory
fallback text; an unavailable gambit has a friendly message.

The **Gambit** selector chooses an existing gambit. **Link** associates it with
the opening; **Unlink** removes that association and retains the gambit. The
separate Gambit maintenance page retains its existing editing workflow.
