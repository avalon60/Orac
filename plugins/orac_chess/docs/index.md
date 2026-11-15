# Orac Chess documentation

Orac Chess owns the private `orac_chess` catalogue schema and the Orac Chess
Explorer APEX application. Its manifest declares database and UI assets
and the optional governed reference query capability. Queries ship disabled pending live data review.

- [Query reference data](reference-query.md): chat and session-bound Query Chess, supported scope and release gates.
- [Administration](administration.md): application workflows, public APIs,
  installation, access boundaries and maintenance.
- [PGN move viewer](pgn-viewer.md): browser replay, variation exploration, local assets and maintainer API.
- [Schema design](schema-design.md): relational model, catalogue ownership and
  forward migrations.
- [Comprehensive catalogue mapping](comprehensive-catalogue.md): pinned source, stable identities, hierarchy, coverage and explicit omissions.
- [Refresh installation seeds](bootstrap-seeds.md): save APEX-maintained data
  with `refresh_seeds.py`, check generated files, and consult historical CSV batches.
- [Verification](verification.md): recorded deployment evidence and outstanding
  checks.
- [MLE deployment scope](mle-deployment-scope.md): production validator assets
  and deployment boundaries.
- [MLE feasibility](mle-feasibility.md): earlier validator investigation and
  diagnostic evidence.

The [current seed refresh workflow](bootstrap-seeds.md) captures APEX-maintained
reference data, catalogue relationships and videos into portable repeatable seeds.
