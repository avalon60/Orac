# MLE integration deployment scope

Prepared on 06-Nov-2026; current application references updated on 08-Nov-2026
after the separately authorised ID correction. These are reviewable commands
for explicit runtime approval; preparing this file did not execute them.
Preserve existing DEV FREEPDB1 data, Liquibase history, alias/receipt and installed
application **10030**. Former application 100 has been removed.

## Managed upgrade and repeat

```text
bin/orac-plugin.sh install --bundled orac_chess
bin/orac-plugin.sh check orac_chess
bin/orac-plugin.sh install --bundled orac_chess
bin/orac-plugin.sh check orac_chess
```

The host reconciles CREATE MLE only for plugin `orac_chess`, schema `ORAC_CHESS`,
using its existing SYS-backed provisioning path. It does not grant that privilege
to other plugin owners or consumers. Seven private runtime objects are installed:
three MLE modules, one PURE environment, three typed call specifications. Existing
validation/public bodies and the final compile/smoke pass are reapplied. The
host imports the editable export using the existing receipt and application 10030.

Check object validity and data/history counts before and after. No checksum reset,
schema reinstall, application-ID migration or blanket privilege grant is included.

## Rollback acceptance

The saved consumer alias below requires the task-specific exception to its
normal connection usage. Its actual login must be ORAC_APX_PUB. SYSTEM execution
does not prove consumer grants.

```text
sql -name orac-db @plugins/orac_chess/db/acceptance/verify_mle_runtime.sql
sql -name orac_apx_pub @plugins/orac_chess/db/acceptance/verify_admin_api.sql
sql -name orac_apx_pub @plugins/orac_chess/db/acceptance/verify_mle_unavailable.sql
sql -name orac-db @plugins/orac_chess/db/acceptance/verify_apex_sources.sql
```

The runtime corpus executes45 cases through the production facade. Public CRUD
fixtures are rolled back. The unavailable-runtime check changes
MLE_PROG_LANGUAGES only in its own SQLcl session, requires the parameter to be
session-modifiable and permitted, and exits the session immediately. Unsupported
parameter/privilege is a failed prerequisite, never evidence of success.

## Coordinated concurrency

Run `concurrency/mle/setup.sql` once through the approved consumer alias, then
`parent_child_a.sql` in one SQLcl session and `parent_child_b.sql` in another while
A holds its45-second transaction lock. Repeat with `competing_roots_a.sql` and
`competing_roots_b.sql`. Run `cleanup.sql` last, including after a failed test.
All paths are under `plugins/orac_chess/db/acceptance/`.

Setup/cleanup commit two reserved openings (`__MLE_CONC_PARENT`,
`__MLE_CONC_ROOTS`) and their reserved variations (`__MLE_CONC_MAIN`,
`__MLE_CONC_ALT`, `__MLE_CONC_ROOT_A`); they require explicit approval for those
committed temporary fixtures. Setup refuses collisions. Do not use cleanup to
remove pre-existing records after a collision; inspect them first.

## Recovery and managed reapplication

Import the generated read-only recovery export through the same host importer,
with the explicit current application ID and receipt checks:

```text
docker cp plugins/orac_chess/apex/recovery/orac_chess_admin_readonly.sql orac-db:/tmp/orac_chess_admin_readonly.sql
docker exec orac-db env ORACLE_PDB=FREEPDB1 /home/oracle/orac/bin/install-plugin-apex-app.sh --plugin-id orac_chess --plugin-version 0.2.0 --app-alias ORAC_CHESS_ADMIN --workspace ORAC --parsing-schema ORAC_APX_PUB --export /tmp/orac_chess_admin_readonly.sql --entry-page-id 1 --application-id 10030 --replace-existing
sql -name orac-db @plugins/orac_chess/db/recovery/mle/withdraw.sql
```

Withdrawal restores fail-closed bodies and verifies them before removing the
private MLE objects. It does not delete tables/data/history or revoke pre-existing
privileges. Reapply the ordinary managed upgrade commands above: runtime objects
and the affected validation/writer bodies deliberately use runAlways as well as
runOnChange, so withdrawal is repaired without altering historical checksums.
Repeat runtime and consumer rollback checks after reapplication.

## Remaining release evidence

An approved isolated fresh target is still required; do not invent or provision
one from this document. An existing authorised browser session is needed to
verify editable rendering, layout, save/cancel/delete, LOVs, modal refresh and
fill-empty metadata. utPLSQL is absent and its separate topology/provisioning is
unresolved. None of these gaps is closed by local source tests.
