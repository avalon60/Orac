# Isolated MLE feasibility proof

This diagnostic evaluates chess.js 1.4.0 with Orac's strict PGN policy under
Oracle MLE. It does not change the installed validator, enable writers, grant
application access, or participate in the plugin Liquibase controller.

Verified locally: the portable corpus contains every one of the 29 Java spike
checks, plus 10 additional rejection/acceptance checks. The Node runner also
checks header extraction, complete input consumption, divergent branch rules,
exact 4,194,304-character input and 64-level RAV nesting limits. Database
installation and execution passed after explicit approval on 06-Nov-2026;
see the runtime evidence below.

The upstream ESM release file is renamed `chess.mjs` without changing bytes.
`vendor/chess.js-1.4.0/PROVENANCE.json` records the release URL and SHA256,
individual file hashes and update policy. The BSD licence is preserved.
Repository-owned policy and Oracle bridge code remain under `tools/mle`.
Generated installation scripts assemble static CREATE MODULE statements in
CLOBs from UTF-8 hexadecimal chunks. This preserves JavaScript backslashes
through SQLcl; the diagnostic JSON request uses the same transport. Each
module must be VALID before installation proceeds to the environment.

## Local verification and regeneration

```bash
node plugins/orac_chess/tools/mle/run.mjs
python3 plugins/orac_chess/tools/generate_mle_proof.py --check
```

To reproduce the upstream bytes, download the exact tarball URL in the
provenance record, verify its SHA256, and compare `package/dist/esm/chess.js`
with `vendor/chess.js-1.4.0/chess.mjs`. The package does not record a commit;
provenance explicitly records that limitation. Regenerate SQL without `--check`
after an intentional adapter change.

## Approval scope and execution

Approval is needed for privileged DEV DDL through saved connection `orac-db`
(`SYSTEM`), in `FREEPDB1`. No schema creation, grants, role changes, data DML,
application deployment, public synonym, or writer enablement is requested.
Scripts qualify every stored object with `ORAC_CHESS`; they do not use
`alter session set current_schema` as a privilege mechanism.

Run the scripts from SQLcl in this order after approval:

```sql
@plugins/orac_chess/db/diagnostics/mle/install.sql
@plugins/orac_chess/db/diagnostics/mle/test.sql
@plugins/orac_chess/db/diagnostics/mle/cleanup.sql
```

The exact temporary stored objects are:

| Name | Type |
| --- | --- |
| `ORAC_CHESS.CHESS_MLE_PROOF_SMOKE` | Function; inline PURE arithmetic |
| `ORAC_CHESS.CHESS_MLE_PROOF_LIB` | MLE module; unchanged chess.js |
| `ORAC_CHESS.CHESS_MLE_PROOF_POLICY` | MLE module; strict PGN policy |
| `ORAC_CHESS.CHESS_MLE_PROOF_BRIDGE` | MLE module; CLOB boundary |
| `ORAC_CHESS.CHESS_MLE_PROOF_ENV` | PURE MLE environment |
| `ORAC_CHESS.CHESS_MLE_PROOF_RUN` | Function; CLOB call specification |

The install preflight checks `DBA_OBJECTS` for all six names and refuses any
collision. It uses `create`, never `create or replace`. The first arithmetic
call must return 42 before the library is installed. SYSTEM's existing
privileges must suffice; failure is a diagnostic result and must not trigger
automatic privilege escalation or owner grants.

The database test passes the same 39 portable cases from PL/SQL through genuine
CLOB input/output, plus five runtime cases: depth 64/65, exact size 4 Mi/4 Mi+1,
and a legal PGN with a comment exceeding 64K. It checks the header extraction
result and separately exercises returned CLOB data exceeding 64K. Runtime
success is reported only after expected validity matches all 44 cases.

Cleanup is repeatable after a partial installation. It skips missing names,
refuses unexpected object types and drops only the six exact names in reverse
dependency order. Oracle DDL commits; a failed installation therefore still
requires cleanup. Keep the install/test error output, execute cleanup, and
verify no names remain in `DBA_OBJECTS`. No existing validator object is touched.

## Policy and remaining evidence

The tokenizer consumes the entire document. The adapter replays every nested
RAV from the position before its preceding move, requires exact canonical SAN,
checks move numbers and terminal results, and checks FEN/header consistency.
Relational variations contain one mainline. Branches share the required move
and position prefix and differ at the next half-move. Exceptions reject input.

The existing Java candidate and its authoritative policy are intentionally
preserved; the Java candidate is inactive and public writers remain gated. This is an alternative
runtime proof, not a migration or a declaration of complete equivalence for all
possible PGNs. Integration still requires managed migrations, execution through
the plugin's least-privileged API path, downstream acceptance, authenticated
browser workflows and fresh-install verification. No performance comparison
against Java or exhaustive PGN equivalence claim is made.

## Oracle runtime evidence — 06-Nov-2026

Explicitly approved execution used host SQLcl and CSV-mapped DEV provisioning
connection `orac-db`: `SYSTEM`, database/container `FREEPDB1`, Oracle AI Database
26ai Free version `23.26.0.0.0`. SYSTEM was needed to create the six diagnostic
objects in the existing plugin schema without granting new owner privileges.
No grants, application changes, controller wiring or business data DML ran.

| Check | Observed result |
| --- | --- |
| Inline PURE arithmetic | Returned 42 successfully |
| Stored library, policy and bridge modules | All VALID |
| PURE environment and CLOB call specification | Both VALID |
| PL/SQL runtime corpus and boundaries | `MLE_PROOF_PASS: 44 corpus/boundary cases; CLOB input/output >64K` |
| Clean removal, reinstall and repeat corpus | Passed; repeat test block elapsed 4.788 seconds, not a throughput benchmark |
| Diagnostic object grants | Zero |
| Final diagnostic objects remaining | Zero |
| Final invalid ORAC_CHESS objects | Zero |

The first inline source load was INVALID: SQLcl altered JavaScript backslash
escapes, producing a syntax error in the library. The partial installation was
removed and absence verified. UTF-8 hex/CLOB loading then preserved source
bytes and both subsequent installations passed. The dictionary reports the
environment type as `MLE ENVIRONMENT`; the cleanup guard was corrected to that
exact type before full cleanup. Generated assets include both corrections.

Local Node corpus/boundary checks and deterministic generator checks also
passed. Runtime transcripts are in `/tmp/orac-mle-proof-install.log`,
`/tmp/orac-mle-proof-install-retry.log` and `/tmp/orac-mle-proof-repeat.log`;
these are local transient evidence, not repository dependencies.

Conclusion: this pinned MLE candidate is feasible on the tested DEV database.
At the end of this isolated proof the public game/variation APIs and read-only
forms remained unchanged and gated. Subsequent integration source and its pending
acceptance are recorded in [verification](verification.md).
Independent review was disabled in the balanced profile; no separate tester
was configured. This result is a feasibility gate, not release acceptance.

Oracle references: [PURE restrictions and syntax](https://docs.oracle.com/en/database/oracle/oracle-database/26/mlejs/restricted-execution-contexts.html),
[CLOB handling](https://docs.oracle.com/en/database/oracle/oracle-database/26/mlejs/large-objects-lob-mle.html),
and [OracleClob API](https://oracle-samples.github.io/mle-modules/docs/mle-js-plsqltypes/26ai/classes/IOracleClob.html).
