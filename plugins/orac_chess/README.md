# Orac Chess plugin

The plugin owns a private relational schema and controlled maintenance APIs,
with the Universal Theme **Orac Chess Explorer** application. See
[administration](docs/administration.md) for pages, API boundaries, validation,
security, installation and testing, and [schema design](docs/schema-design.md)
for the authoritative relational model and baseline history.

Version 0.3.0 adds the disabled [reference query capability](docs/reference-query.md)
and Query Chess page 120, with a separate Core live data review gate. It retains
the existing administration application access and maintenance controls.

The 0.2.0 administration changes are additive upgrades to the 161-changeset
baseline. They do not rewrite deployed baseline history.

The user-authorised 01-Nov-2026 amendment adds `CHESS_OPENING.OPENING_TYPE` to
the original CREATE TABLE: `varchar2(20 char) default 'OPENING' not null`, with
`CHS_OPN_TYPE_CK` permitting `OPENING` and `SYSTEM`. Both classifications share
the same identity, hierarchy, ECO codes and related records. Reclassification
does not change their relationships or variation ownership type (`O`).

This source amendment applies to fresh installs only; it is not an upgrade for
the former 160-changeset baseline and must not be reconciled by resetting checksums.
On 01-Nov-2026, the user-authorised managed reinstall replaced the verified empty
development schema in FREEPDB1. All 161 changesets executed, managed readiness and
the structure, semantic and hierarchy checks passed, and temporary test rows were
rolled back. Historical Core knowledge was preserved. The 0.2.0 administration release adds forward migrations after this baseline.

The source now integrates the pinned chess.js 1.4.0 validator as private PURE
Oracle MLE modules, typed call specifications and controlled public writers.
The earlier Oracle Java compatibility failure remains diagnostic history.
The isolated proof and approved DEV managed integration, production/consumer
acceptance, concurrency and withdrawal/reapplication checks passed. Fresh isolated
installation, authenticated browser workflows and utPLSQL remain outstanding.
The authorised application-ID correction on 08-Nov-2026 removed former application
100 and installed the enhanced application as 10030 with a fresh host receipt.
The manifest now explicitly declares 10030. See
[administration](docs/administration.md) and [verification](docs/verification.md).

Content Sources now provide a maintained Creator or Publisher list with Author
and editable Notes. Videos select an existing source while keeping their existing
string creator field; multiple videos can share one creator. The forward
migration inserts five initial sources and preserves every existing video creator
without rewriting video rows. See [schema design](docs/schema-design.md#content-sources-forward-migration--07-nov-2026)
and the deployment results and remaining checks in
[verification](docs/verification.md#content-sources--deployment-verification-07-nov-2026).

Install and upgrade now apply the immutable `2026_11_07_bootstrap` CSV batch:
44 videos with explicit source identities, blank unknown dates and preserved
prose. Successful batches never replay, so later upgrades preserve user edits
and deletions. See [CSV bootstrap batches](docs/bootstrap-seeds.md) for templates,
generation, release rules, transaction handling and the supplied, unexecuted
isolated database acceptance checks.

The comprehensive reference expansion builds on those released batches using
pinned CC0 Lichess source data: 128 opening/system identities, 612 gambits and a
projected 4,558 variations, including 100 protected prior branches. Native
searchable popup LOVs and additive continuation edges support the larger
collection. The private source-management ledger protects existing subjects,
merges safe updates to newly imported records and exposes a read-only plan with
explicit conflicts. See [mapping and coverage](docs/comprehensive-catalogue.md),
[sync operations](docs/bootstrap-seeds.md#incremental-comprehensive-catalogue-sync)
and [deployment evidence](docs/verification.md) for actual target results and
remaining verification limits.

### Opening ECO selections

On an opening, enter a code or opening name in the search field, then open ECO
codes to select all that apply. Search checks the complete catalogue description;
the popup displays a bounded description. Existing links are selected when the opening is loaded. Save writes
the opening details and selected codes together; Cancel discards both edits.
The administration API accepts the complete colon-separated set through
`save_opening_with_eco`, validates every catalogue code, and leaves transaction
commit or rollback to its caller. The single-code link API remains available.

### ECO reference

Installation now supplies all 500 ECO codes A00–E99 in `CHESS_ECO_CODE`. Each
CLOB description contains all distinct English opening names for that code
from a pinned CC0 source, sorted and separated by newlines. The seed inserts
missing codes and preserves existing descriptions. `CHESS_ECO_CODE_V` provides
SELECT access for `ORAC_APX_PUB`. See [bootstrap seeds](docs/bootstrap-seeds.md#eco-reference)
for provenance, regeneration and update policy.
