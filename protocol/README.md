# Orac Protocol – Release & Versioning Guide

This folder contains the canonical **protocol schema** and **validator** packaged as `orac-protocol`.
Clients (e.g., **Orac-Client**) install it directly from this repo via a **Git tag** (no PyPI).

* Package path: `protocol/` (this folder)
* Schema path: `orac_protocol/resources/json_schema/protocol.schema.json`
* Version file(s):

  * `protocol/pyproject.toml` → `[project].version`
  * `orac_protocol/__init__.py` → `SCHEMA_VERSION`

We use **semantic versioning**:

* **MAJOR**: breaking changes to the wire format
* **MINOR**: backward-compatible additions
* **PATCH**: fixes / clarifications, no API change

---

## 0) Quick checklist (TL;DR)

* [ ] Create a branch from `develop`
* [ ] Update schema + code, bump versions in **both** files
* [ ] Update `CHANGELOG.md`
* [ ] Commit → merge to `develop`
* [ ] Tag: `protocol/vX.Y.Z` on the **merge commit**
* [ ] Push branch + tag
* [ ] Update **Orac-Client** to that tag in `pyproject.toml`
* [ ] `pip install` and sanity-test `validate_frame`
* [ ] (Optional) merge `develop` → `main` to keep main in sync

---

## 1) Make your changes

1. Edit the schema:
   `orac_protocol/resources/json_schema/protocol.schema.json`

2. If you added fields or changed validation logic, update any related code in:
   `orac_protocol/validator.py` (usually unchanged)
   `orac_protocol/__init__.py` (version constant)

3. Bump versions:

   * `protocol/pyproject.toml` → `[project].version = "X.Y.Z"`
   * `orac_protocol/__init__.py` → `SCHEMA_VERSION = "X.Y.Z"`

4. Update `protocol/CHANGELOG.md` with a clear entry:

   * **Added** / **Changed** / **Removed**

---

## 2) Branching model (default branch: `develop`)

### GitKraken

* **Create a feature branch** from `develop`:

  * Right-click `develop` → *Create branch here…* → `feat/protocol-X.Y.Z`
* Make commits.
* **Merge back** into `develop`:

  * Drag `feat/protocol-X.Y.Z` onto `develop` → *Merge into develop*
  * Push `develop`.

### Git CLI

```bash
git switch develop
git pull
git switch -c feat/protocol-X.Y.Z
# … edit files, commit …
git commit -am "protocol: bump to vX.Y.Z; update schema & CHANGELOG"
git switch develop
git merge --no-ff feat/protocol-X.Y.Z
git push origin develop

