### Purpose

High‑level brief so Cline can quickly understand Orac’s scope, why it exists, and how work should be shaped.

### TL;DR

* **Project name:** Orac (retro‑futuristic home AI assistant)
* **Owner:** Clive (Bozzy)
* **Primary goals:**

  1. Conversational assistant + home automation skills layer.
  2. Persisted conversation context (RDBMS + vectors) with pruning bands.
  3. Good developer ergonomics (APEX admin UI, CLI slave client, CI hooks).
* **Non‑goals:** General chat app with no persistence, ad‑hoc coding styles, cloud vendor lock‑in.

### Architecture (current)

* **Database:** Oracle 23ai Free; schemas: `dut_core`, `dqu_core`, API schemas `dut_api`, `dqu_api`, business logic `dqu_code` (not exhaustive). Identity PKEYs + optimistic locking via `row_version`. API views suffixed `_v`. TAPI packages per table.
* **App/UI:** APEX 24.x for admin & dashboards.
* **REST:** ORDS 25.x.
* **Orchestrator:** `orac.py` (Python) routes to LLMs (Ollama / LM Studio connectors).
* **CLI client:** `slave.py` (Zen/Slave) strict JSON‑schema protocol with HMAC.
* **Context manager:** DB tables for users, conversations, messages, embeddings; vector index.
* **Home automation:** Home Assistant on Pi 5; Orac “skills” layer to route intents.

### Dev style & constraints

* British English; concise commit messages; reproducible scripts; prefer **lower‑case SQL/PLSQL keywords**; **2‑space indentation**; Liquibase‑formatted SQL for DDL; logger cross‑cutting.
* Python modules include file headers (`__author__`, `__date__`, `__description__`) + argparse + reST‑style docstrings.
* Prefer `sqlplus` in container builds.

### Repos & important paths

* Example (adjust):

  * `/home/clive/PycharmProjects/Orac` (orac.py, libs, CLI, Docker helpers)
  * `resources/config/` (`orac.ini`, DSN creds)
  * `apex/`, `ords/`, `orac_sql/`, `orac_sh/` under `/home/oracle/orac/` *inside* the container

### Testing strategy

* **utPLSQL** packages in `unit_test` schema; tests grouped by package type.
* Data QA suite: cardinality & pluggable tests via `dqu_suite` with dynamic bind support using `dbms_sql`.
* BDDS Selenium framework for APEX UI (separate project; orchestrator supports parallel runs + reporting).

### Workflows (sketch)

1. **DB change:** DDL → Liquibase file → container `sqlplus` apply → TAPI views/triggers updated.
2. **PL/SQL change:** Update spec/body → regenerate utPLSQL tests via Cline rules → run `ut.run()`.
3. **Python change:** Module with argparse → unit tests → integrate with orchestrator.
4. **Skill change:** Register in skills catalogue → map intents/phrases → e2e with Home Assistant.

### Risks & guiding principles

* Keep context store lean via pruning bands; never lose auditability.
* Prefer table APIs over ad‑hoc DML. Log **everything** (inputs/params/errors).
* One source of truth for credentials (dbconn.py; encrypted).
