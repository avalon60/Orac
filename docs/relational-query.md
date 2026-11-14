# Governed relational queries

Core provides one natural-language SQL service for authenticated chat and
session-bound APEX requests. The first optional dataset is
`orac_chess.reference`, exposed by capability `orac_chess.query`. This is a
relational reference query path: it uses the existing LLMConnector, without
Select AI, embeddings, vectors or a separate model service.

The feature ships disabled. `[relational_query] enabled = false` is the default
when the configuration entry is absent. The Core worker runs retention maintenance even while execution is disabled.
Setting the flag to true allows registration of installed manifest declarations; it does not
verify a dataset or authorise its execution. The original source implementation did not change configuration; the dated
DEV release checkpoints below record its later authorised enablement.

## Eligibility and access

Trusted transports supply `PrincipalContext`; the model and plugin payload
cannot choose the username. Anonymous and reserved principals are rejected.
Every authenticated Orac user is eligible for chat subject to existing
interface access, enabled installed plugin state, the declared capability,
caller capability restrictions and a matching verified dataset. Chat does not
look up ORAC_ADMIN, hub ACL membership or a new query role.

The Chess application remains application 10030 in workspace ORAC, parsing
schema ORAC_APX_PUB. Its manifest retains the existing ORAC_ADMIN application
access declaration, and its maintenance pages retain Administration Rights.
Query Chess page 120 and both AJAX callbacks use those same existing access
controls. This does not broaden the administration application's audience.
Queued execution reapplies the installed application's declared roles, and
submission/delivery use the current APEX authentication and Administration
Rights scheme. App/user/session come from APEX session context, never page items
or generated SQL. Chat eligibility is independent of those application roles.

The dataset catalogue stores lifecycle and live review evidence, not user
permissions. No user, role or ACL assignments belong in that table. Future
RBAC belongs at Core eligibility before metadata access, execution and queued
result delivery; it is intentionally not implemented here.

## Declaration and metadata

Optional `query_datasets` manifest entries contain only version 1, dataset ID,
capability ID, metadata version and explicit schema-qualified view/column
references. Discovery rejects extra fields, foreign schema ownership, duplicate
IDs/columns and undeclared capabilities. Declarations contain no SQL, grants,
credentials, endpoints or administrator roles.

Core loads metadata only after eligibility. It requires exact installed view
columns and one same-owner table dependency per view. Column/table comments and allowlisted annotations are filtered to the
projection. Primary/unique/foreign-key metadata comes from a separate immutable
operator-reviewed snapshot in the existing catalogue evidence, because the
bridge cannot see base-table constraints. Composite key column order and
target columns are preserved.
Annotations cannot expand execution authority. Oracle documents that the
[annotation owner matches the annotated object owner](https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/USER_ANNOTATIONS_USAGE.html); metadata filters that owner, exact object and projected columns. Metadata cache identity includes the canonical snapshot digest. Each admitted
request checks live view columns/types and same-owner table dependencies against
the review, even on a cache hit. Plugin manifest/state changes invalidate it. Results are never
cached. Installation changes the manifest fingerprint and resets the live gate;
a changed dataset requires a metadata version change and review.

## SQL and resource controls

SQLGlot 27.28.1 is pinned in pyproject and lock file. The validator checks every
AST node and populated argument, all SELECT scopes and every column expression,
source views, named scalar binds and approved functions. It serialises and
reparses before the canonical SQL reaches the executor. Parsing alone grants no
authority. Unsupported syntax fails closed; user questions never bypass model
output validation.

Supported queries include non-recursive CTEs/subqueries, EXISTS, explicit joins,
filters, grouping, HAVING, ordering and bounded FETCH. CONNECT BY requires
NOCYCLE, an explicit start condition, the reviewed same-owner edge expression
and LEVEL <= 32. Arbitrary expressions, functions/packages, PL/SQL, DDL/DML,
links, synonyms, hints/comments, locking, flashback and multiple statements are
denied. One validation correction is allowed: transient feedback contains the
rejected SQL/binds and a safe static explanation of its validator code, marked
as untrusted candidate data. Database errors are never sent back to the model,
and a second rejected candidate fails closed. No raw candidate is added to
production audit events.

Limits are 2,048 question characters, 16 KiB generated SQL, 60 seconds per model
attempt, 10 seconds overall SQL execution, 500 rows, 1 MiB encoded rows and
columns, hierarchy depth 32, two active queries per dataset, 30 admitted queries
per principal per hour and two outstanding per principal. Core admission uses
CODE-owned database operations shared by chat and APEX, with a fixed catalogue
lock order. An APEX claim reuses its admission rather than counting twice.
Generation has two bounded provider slots. A timed-out provider retains its
slot until it returns; additional abandoned work is not queued indefinitely.

The dedicated Core executor opens a disposable raw driver connection using the
existing `database.plugin_dsn_credential_entry` (default `orac-plugin`), checks
both credential username and actual session user ORAC_PLUGIN, starts a read-only
transaction, fetches incrementally, and rolls back/closes on every exit. It does
not call plugin facade call_plsql/callproc/fetch_dicts. There is no result pool.
A wall-clock deadline returns QUERY_TIMEOUT and cancels the driver. A stalled
cancellation retains one of two physical executor slots until cleanup finishes;
it cannot create unlimited SQL workers. Connection establishment uses bounded
Oracle TCP connection options and belongs inside the overall caller deadline.

ORAC_PLUGIN remains a shared bridge identity with other approved plugin
privileges. Oracle grants alone do not isolate datasets: the Core validator and
lifecycle eligibility are the isolation boundary. Review effective privileges,
view definitions/dependencies and callable functions before release. Do not
claim this bridge has an independently sandboxed per-dataset Oracle account.

## Queue, retention and installation

Core table/API/CODE layering is preserved. The production chain is
`resources/db/schema/install.sql` (or `install_orac.sql`) ->
`productController.xml` -> orac_core/orac_api/orac_code schema controllers and
their typed includeAll directories. New catalogue, request and audit tables
have separate key/check/index/comment assets. API views receive Core privileges
before creation. Only the APEX package is granted to ORAC_APX_PUB; only the
worker package is granted to normal ORAC. ORAC_PLUGIN receives no Core table
access. Post-install recompilation resolves existing CODE-view ordering.
Core installation contains no reference to an optional Chess schema.

Chess adds controller `16_query_reference.xml` after the released controller
chain. It creates separate explicit query views and READ grants to ORAC_PLUGIN;
existing objects, data and released changeset identities remain intact.
Each new object/grant has its rollback. Rollback of the new queue tables removes
transient query payloads/audit only, and must be an explicit deployment decision.

The separate relational queue stores principal, app, APEX session, dataset,
metadata version and manifest fingerprint. Only current owner/token/unexpired
leases can complete. Worker execution and completion recheck plugin, app and
session eligibility; late/stale results are discarded. Readback is restricted
to the same user/app/session, with current access rechecks. Requests and their
questions/results expire after one day. The scheduled worker purges them and
content-free audit records older than 30 days. Audit includes principal,
dataset/version, model, SQL fingerprint, outcome, duration, row count,
truncation and correlation, without raw question, SQL, binds or result values.
If the Core worker is stopped, an operator must run the existing worker
purge procedure under the normal service identity to maintain retention.

## Prose answers and reviewed evidence

The shared Core service generates one explanation after successful retrieval,
using the existing connector and physical provider slots. Results add
`catalogue_answer`, `general_knowledge_answer` and `answer_status`; existing
rows, canonical SQL and provenance remain available. APEX and handled chat
present these answers directly without a second synthesis call. Clarifications
and unsupported questions retain their existing messages.

Catalogue explanations are model interpretations of returned evidence; they
are not a guarantee of factual accuracy. Supplementary general chess knowledge
is separately labelled and must not be presented as stored catalogue facts.
Stored descriptions and PGN are untrusted data, never model instructions.
Successful empty retrieval may receive general context; authorisation,
availability and SQL failures never fall back to a general answer.

Synthesis receives at most 32 KiB of evidence, including the successfully
executed canonical SQL, scalar binds and a whole-row result prefix. Selection
context is never silently removed: if SQL/binds/columns alone exceed that
bound, synthesis is skipped while the successful table remains available.
Each plain-text answer section is limited to 4 KiB UTF-8. Evidence clipping is
explicit. Synthesis failure preserves successful table results with
`answer_status=unavailable`; private errors are not returned. Eligibility is
rechecked before disclosure and before delivery. A 150-second monotonic
service budget bounds SQL generation, execution and synthesis: attempts remain
at most 60 seconds, a correction requires reserve for execution/answer/cleanup,
SQL remains at most 10 seconds and synthesis at most 20 seconds with no retry.
The scheduled worker allows 170 seconds around the service; the three-minute
claim lease and 200-second APEX polling window remain unchanged.

Chess metadata version 2 adds three single-table read-only projections for
opening/gambit descriptions and variation move context, preserving the first
nine views. SQL SUBSTR plus VARCHAR2 casting limits CLOB text to 1,000
characters and exposes clipping flags; the executor never reads a raw LOB.
Variation PGN is interpreted with owner, parent, branch ply, line kind and
starting FEN. A continuation is never evidence of a complete opening line.
Annotation, games, media and configuration remain excluded. New metadata and
manifest fingerprints invalidate prior dataset review.

### Query-only Core deployment

All new Core query changesets additionally carry label `relational_query`.
Where unrelated Core deltas are pending, use the existing deployment wrapper
with `--labels relational_query`: validate, inspect `--update-sql`, then apply
only the reviewed query delta. Canonical controller paths and changeset IDs
are unchanged. Do not use changelog-sync, clear checksums, or a container
rebuild to deploy this feature. Deploy the Chess projections through the
managed plugin installer after Core, review actual data and privileges, then
record version-2 evidence and enable execution. Do not seed verification in
installation assets. Disabling execution is the first rollback action; retain
existing data and queue/audit tables.

## Release gate and evidence

Source implementation is not a data classification review. Before enabling a
dataset, an authorised operator must verify actual exposed contents,
provenance/classification, projection definitions, ordered relationships,
installed READ grants, effective bridge privileges and dependencies. Record
review evidence in catalogue `evidence_json`, `verified_on`, `verified_yn='Y'`
through an explicitly authorised database maintenance operation. The runtime
sync API cannot set those fields. A plain configuration flag cannot open the
gate. No source asset seeds a verified dataset.

On 08-Nov-2026 read-only SQLcl used the CSV-mapped DEV inspection connection
`orac`, verifying ORAC/FREEPDB1/current schema ORAC. No CHESS_QUERY objects were
visible. No owner/admin fallback, deployment or enablement was performed.
Actual exposed contents, source suitability, installed grants, Oracle package
compilation, fresh/upgrade/rollback behaviour and authenticated APEX workflows
remain unverified. Those checks are required before release. The read-only
[Chess acceptance script](../plugins/orac_chess/db/acceptance/verify_query_reference.sql)
provides bounded projection/privilege evidence when run through an authorised
connection that can see the target objects; lack of visibility is a failed gate.

Local tests exercise the real validator and service, deterministic synthetic
question-to-SQL responses with real SQLite reference rows, hostile queries,
trusted router identity, lifecycle rechecks, limits and driver cancellation /
cleanup. They do not demonstrate live model accuracy, Oracle semantic execution
or authenticated browser behaviour. Run:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_relational_query.py tests/test_plugin_router.py tests/test_plugin_routing.py tests/test_plugin_service_manager.py tests/test_orac_chess_administration.py tests/test_orac_chess_eco.py tests/test_orac_chess_seed.py tests/test_knowledge_apex_search.py
```

### DEV deployment checkpoint — 12-Nov-2026

The authorised query-only release applied all 34 Core query changesets and
verified VALID query APIs and their intended consumer grants. Managed Chess
installation verifies 12 query views and consumer READ grants; installed APEX
source compilation passes 92 sources. Version-2 declaration registration
succeeded through the normal runtime API, but the dataset remains unverified
and execution remains disabled.

Live collection under ORAC_PLUGIN sees projected view metadata but no
base-table keys or foreign keys. That visibility gap prevents release under
the documented reviewed-relationships contract. No broad dictionary/base
privileges were granted as a workaround. The architecture decision and
remaining live-model, worker, authenticated APEX and isolated lifecycle checks
must complete before enablement. See the dated Chess verification entry for
content inspection evidence and deployment details. Earlier dated unverified
statements above describe their original implementation checkpoints.


### Reviewed constraint snapshot

The operator-selected design stores `projected_metadata` inside the existing
catalogue `evidence_json`; no extra grants, table or plugin metadata API is
introduced. The fixed CODE worker function
`reviewed_metadata(dataset_id, metadata_version, manifest_hash)` returns only
that object after the live verification gate passes, never the surrounding
review evidence. Normal runtime cannot create or mark a review verified.

The exact object fields are `format` (integer 1), `dataset_id`,
`metadata_version`, `manifest_hash`, `review_id`, `views`, `keys` and
`relationships`. A new immutable `review_id` is mandatory for every review
replacement. Each view maps to an ordered `columns` array of `{name,type}`
and `source: {owner,table}`. Names are lower-case, data types match the live
Oracle dictionary. Each key has `{view,columns,kind}` where kind is P or U;
each relationship has `{view,columns,target_view,target_columns}`. Only actual
ENABLED/VALIDATED PK, UK and FK constraints are reviewed; every fully projected
view of the same table receives its eligible keys and actual FK targets.
Sharing a base table does not itself create a foreign-key relationship.

The snapshot must match the complete manifest projection and installed
column/type/dependency signatures. Unknown fields, duplicate JSON fields,
duplicate keys/edges, undeclared columns, mismatched identities and FK targets
without the corresponding ordered key are rejected. Limits are 128 KiB UTF-8,
32 views, 256 keys, 512 relationships and 32 columns per key/edge. The Core
validator computes SHA-256 over sorted-key compact UTF-8 JSON; list order,
including composite-column order, is retained.

Each admitted request fetches a verified snapshot after eligibility. Core
rechecks its digest before SQL execution, synthesis and delivery; replacement
fails closed. Results carry `review_id` and `review_digest` in provenance.
Queued completion and APEX result readback additionally compare the result's
review ID to the current verified review, preventing delivery of old results
after replacement even when manifest/version stay the same.

Live bridge-visible signatures detect changed projections or dependencies.
They cannot detect hidden base-constraint-only changes. The operator must
invalidate verification before such schema changes and regenerate the reviewed
snapshot from actual privileged dictionary evidence. This is an explicit
review lifecycle requirement, not a claim of continuous base-schema drift
monitoring. Review IDs must never be reused for changed snapshots.

Query recompilation and validity guards now run on every managed Core update,
so a changed package body cannot bypass an unchanged post-install validator.
The separate APEX knowledge query lifecycle checks use the existing CODE
registry projection for removal state; no new owner-table access is added.

Runtime enablement is resolved from the authoritative installed registry row,
not the packaged manifest's installation default. Enabled-manifest loaders
return an effective enabled copy only after full registry eligibility and
artifact/hash validation. Inspectors and source payloads retain their declared
default, and registry-disabled, failed or removal-fenced rows remain excluded.

### Live backend checkpoint — 12-Nov-2026

After the reviewed-snapshot implementation and authorised review operation,
DEV verification and query execution are enabled. The active review contains
12 view signatures, 23 projected keys and 33 explicit relationships. A live
configured-Ollama backend request returned five Evans Gambit records and both
prose sections with matching review provenance. The managed query worker is
running. This supersedes the earlier same-day gate-closed checkpoint; it does
not establish authenticated APEX queue/browser or isolated lifecycle acceptance.
A sampled supplementary statement incorrectly described a gambit capture as
forced, so the synthesis prompt now explicitly requires optional-acceptance
language. Prompt tests do not guarantee factual model output.


A further live relationship question correctly retrieved Italian Game through
an EXISTS/join query but the model incorrectly denied the association when it
saw only projected names. Synthesis evidence now includes executed SQL and
scalar binds so those projected rows retain their selection semantics. Prompt
rules explicitly preserve nonempty matching relationships, limit zero-row
claims to the executed query and avoid unsolicited historical dates or
biography. Executable adapter tests verify the actual validated SQL/binds flow
and combined evidence bound; they do not prove model semantic accuracy.

Signed chat routing additionally requires the dedicated semantic
`[plugin_routing]` embedding profile documented in configuration. Production
bootstrap no longer constructs the non-semantic hash test fixture. Routing
cache identity is isolated from other embedding uses; intent text, thresholds,
arbitration and capability policy are unchanged. Low-confidence unaddressed
questions may still clarify or use ordinary chat. Existing explicit plugin
addressing can select eligible Chess queries without lowering thresholds.

For questions already fully answered by catalogue rows (relationship lists or
counts), supplementary general knowledge may be empty. Synthesis instructions
avoid unnecessary background or move claims. A live relationship answer became
correct after selection context was supplied, but supplementary prose still
introduced an incorrect pawn-square claim; this reinforces the distinction
between operational acceptance and factual model accuracy.

### Final backend and signed-chat checkpoint — 12-Nov-2026

The reviewed full Core run reported 53 changeset executions including recurring
guards; snapshot verification and query execution are enabled, and the managed
worker is active. Signed chat using existing explicit Chess addressing selected
the query capability and returned Italian Game with supporting rows and SQL.
Measured lower-confidence unaddressed questions still clarified or used ordinary
chat under the unchanged routing policy.

Direct backend acceptance includes unsupported non-chess scope, a correct
no-match catalogue response and a final Evans explanation using 47 real rows.
That explanation correctly used b4/Italian Game/C51 and explicitly reported
clipped synthesis evidence. Successful answers with an empty supplementary
field now display the General chess knowledge section with the host-authored
note “No supplementary general chess knowledge was used.”; unavailable synthesis
or unsupported/clarification outcomes do not display that successful-answer
note. This defines presentation of the separate answer field, not a guarantee
of model reasoning or factual accuracy.

Authenticated APEX queue/browser acceptance and isolated fresh-install/rollback
acceptance remain outstanding. Successful backend and signed-chat results must
not be represented as proof those remaining paths passed.

The final renderer managed import respected the live runtime lock: the initial
attempt was refused, Orac was stopped through its lifecycle and the subsequent
import succeeded without changing the manifest fingerprint. Restart and
post-import gate/worker verification remain separate checks. A fresh APEX login
is required after import. Local release regression coverage is 318 tests plus
28 subtests; authenticated APEX queue/visual and isolated fresh-install/rollback
acceptance remain explicitly unverified.


### Overview query scope and APEX evidence disclosure — 13-Nov-2026

Definition/overview generation selects only the matching entity text evidence:
name, description, strategy and required clipping flags. Relationships and move
context are joined only when requested, rather than expanding a simple entity
explanation into repeated variation rows. Ambiguous matches and explicit
variation/list requests retain their records; DISTINCT, arbitrary first-row
selection or client deduplication must not hide a join fan-out mistake.

APEX page 120 prioritises prose and keeps all returned rows/columns inside a
native Supporting records (N) disclosure. It starts closed for actual prose,
opens for unavailable synthesis or absent actual answer text, and preserves
SQL in its separate closed disclosure. Readable-width table cells scroll
horizontally within a keyboard-focusable region. Chat rendering, metadata
version 3, strategy projections, validator authority and review state are
unchanged by this focused update.


### Shared-relationship query reliability — 13-Nov-2026

Generation explicitly prohibits statement terminators, comments/hints, links
and other unsupported constructs, requires exact metadata view names and
qualifies ordinary column references. Projected ORDER BY aliases and required
unqualified columns in the exact reviewed CONNECT BY edge retain their existing
special rules. “Shared” relationships require at least two distinct source
entities through the reviewed junction, not merely any relationship row.

The validator now resolves columns in the nearest permitted lexical scope,
then eligible correlated parents. A local alias shadows its outer namesake;
local ambiguity is still rejected, and CTE/derived-table boundaries do not leak
outer columns. This repairs a valid nested IN/GROUP BY query previously denied
because outer columns were flattened into the inner scope. Dataset, column,
function and statement authority are unchanged.

The final captured configured-runtime batch completed five of five shared-gambit
queries on the first generation attempt, each returning the three expected
Queen's Gambit openings in 15.84–16.04 seconds. SQL used a reviewed same-target
EXISTS condition excluding identical opening IDs. Three generation-only samples
also validated on their first attempts. An earlier intermediate two-run batch
had one SQL_SYNTAX denial; its exact generated candidate was not captured, and
subsequent private diagnostics did not reproduce the forbidden token. No
normalization or relaxation was added on that incomplete evidence. These samples
do not guarantee every future model output will pass validation.
