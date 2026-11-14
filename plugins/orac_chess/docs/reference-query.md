# Query Chess reference data

Orac Chess declares the optional `orac_chess.reference` dataset and
`orac_chess.query` conversational capability. It is disabled by default and
requires the Core live dataset review gate before use. See the
[Core query contract](../../../docs/relational-query.md) for configuration,
security boundaries, limits, queue retention and release verification.

Authenticated chat users can ask reference questions without an administration
role. Example questions are “Which openings share this gambit?”, “What aliases
belong to this opening?” and “List this opening's explicitly assigned ECO
codes.” The model may request clarification or report unsupported scope.

In the existing Orac Chess Administration application 10030, open **Query
Chess** (page 120), enter a question and select **Ask Chess**. A session-bound
background request returns two primary plain-text sections, **From the Chess
catalogue** and **General chess knowledge**. Supporting rows are retained under
**Supporting records (N)**, initially collapsed when an explanation is present.
Canonical SQL remains in its separate **View query SQL** disclosure. The first section explains retrieved evidence; the second
is supplementary model knowledge, not stored catalogue facts. If synthesis
fails, the page still shows successful query rows and an explanation-unavailable
notice. A failed query never silently becomes a general-knowledge answer.
The page uses a native APEX question field and **Ask Chess** action in a themed
region, with a separate Results region. Blank questions receive a local prompt
and focus returns to the field. The action remains disabled while submitting,
queued or processing. Polling runs every two seconds for at most 100 reads;
a still-pending request asks the user to submit again later. Transient status-read
failures receive at most two retries per query, after two then four seconds,
using the existing request ID. Retries count towards the 100-read limit and do
not reset after a successful poll. The action stays disabled during retries.
Submission is never automatically retried. Authentication, access, APEX response,
parse, cancellation and other non-transient failures stop immediately. Completed results
show a row count or empty-result message, with explicit truncation when needed.
Supporting records open automatically if synthesis is unavailable or neither
actual answer field contains prose; the empty supplementary-field placeholder
alone does not hide the evidence. The full table retains every returned row
and column. Wide tables scroll horizontally with readable wrapping cells and
a keyboard-focusable scroll region. Headings, cells, refusal messages and SQL
use literal text.

Failure messages distinguish a request that could not start, a status that
could not be retrieved, a failed query and an expired query. Start failures and exhausted status reads advise reloading the page and signing
in if prompted, then contacting an administrator if the problem continues.
HTTP 401/403 responses report that sign-in or access could not be verified;
APEX or JSON parse failures report an unreadable response with the same reload
and sign-in guidance. The page does not redirect automatically. These messages do not diagnose the
cause or expose operational errors. Administrators must verify installation,
API access and the Core query release gates separately. All terminal outcomes
restore the action so the user can retry.
The existing ORAC workspace, ORAC_APX_PUB parsing schema, APEX accounts
authentication, manifest ORAC_ADMIN application access and Administration Rights
controls are retained. Existing maintenance direct URLs and writer APIs are
unchanged. Users outside that application audience can still use eligible chat.

Twelve separate query views expose only opening IDs/names/type/parent, aliases,
gambit IDs/names, opening-gambit associations, direct opening/gambit/variation
ECO relationships, upstream ECO code/description and variation
IDs/owners/type/parent/branch ply/name/line kind. Metadata version 3 includes
reviewed opening/gambit descriptions and PGN move context through three
separate views. Text is limited to 1,000 characters with explicit clipping
flags; move context includes starting FEN and ownership/branch information.
Annotation, row versions, games, media, configuration and audit remain excluded. The ECO catalogue description is an upstream name, never a canonical
opening name. SYSTEM is an opening classification with the same explicit
relationships. A gambit may belong to multiple openings. Opening hierarchy and
variation hierarchy are distinct; variation ancestry retains its opening or
gambit owner. Multiple ECO assignments and missing ECO rows are explicit facts.
No transposition inference or inherited ECO assignment is supported.

Install Core query assets before the existing managed plugin lifecycle imports
the application. Plugin controller 16 adds the narrow views, comments and READ
grants without changing released migrations or data. Export/import application
10030 through the existing host receipt path, as described in
[administration](administration.md). The read-only recovery export is regenerated
with the maintained MLE recovery generator and includes the query page.

The live data suitability and grant gates remain **unverified**. No deployment
or enablement was performed in this implementation pass. Existing DDL and
upstream provenance are evidence to inspect, not proof that every stored value
is suitable for model disclosure. A live model, installed Oracle execution and
authenticated session/forgery/expiry/browser checks are still required. Local
acceptance uses synthetic reference contents and a deterministic model adapter;
it demonstrates relational semantics and security boundaries only.

Local regression checks verify native controls and accessible status settings in both exports and
execute each export's page JavaScript with mocked APEX callbacks, DOM elements
and timers. These checks cover submission, queued/processing polling, results,
truncation, literal text rendering, refusal, missing request IDs, malformed payloads, blank questions, duplicate clicks,
stale callbacks, transport errors, expiry and polling timeout. They do not verify an imported APEX page or its
rendered browser layout. Import and authenticated browser verification remain
blocked on the live release checks above; this repair does not enable queries.


### Version 2 release requirements

Controller 19 appends the bounded explanation projections after controller 16.
The metadata version and manifest fingerprint change requires a fresh live
review of actual descriptions and PGN before model disclosure. Descriptions
and PGN are untrusted input; clipped lines and continuations must never be
presented as complete move sequences. Core service deployment is separate from
successful Chess managed readiness. Follow the Core query-only deployment
procedure and preserve the release gate until actual contents, grants and
consumer behaviour pass. Source tests do not establish live readiness.


Version 2 also requires a Core-reviewed projected-constraint snapshot in the
existing dataset evidence. Runtime reads column/dependency signatures as the
bridge, then uses only reviewed projected keys and relationships. No base-table
or broad dictionary access is granted. A changed immutable review invalidates
in-flight and stored result delivery. Operators must invalidate the gate for
base-constraint changes, which are invisible to the bridge. See the Core query
contract for the exact snapshot schema and bounds.

### Stored strategy evidence

Opening and gambit text views expose independent `strategy` and
`strategy_truncated` columns. Strategy is bounded to 2,000 characters, with `Y`
when the stored CLOB exceeds that bound. Existing description projections retain
their 1,000-character bound and independent truncation flag. These are stored
catalogue evidence; they must remain distinct from supplementary model knowledge.


### Overview questions and detailed evidence

For a definition such as “What is the Evans Gambit?”, query generation requests
the matching entity name, description, strategy and their clipping flags from
the reviewed text view. It avoids unrelated opening, ECO or variation joins and
unnecessary ID output unless the question asks for relationships, move lines or
those columns. Ambiguous matching entities are preserved or clarified. Explicit
variation/list questions still return their requested records; neither SQL
shortcuts nor the page deduplicate or arbitrarily discard rows to hide fan-out.

This presentation and query-guidance update preserves metadata version 3,
its reviewed strategy projections and the existing dataset release gate. The
shared generation guidance also applies to chat; chat presentation is unchanged.
