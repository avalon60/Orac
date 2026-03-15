## Orac SQL House Style (Authoritative)

- Layout: `resources/db/schemas/<object_type>/<object_name>.sql`
- One object per file. Filename = **object_name.sql** (no schema prefix).
- **Lowercase** SQL keywords; **2-space** indentation.
- **Do not** inline constraints in `create table`:
  - Primary keys → `constraint_pk/`
  - Unique constraints → `constraint_uc/`
  - Foreign keys → `constraint_fk/`
  - Checks → `constraint_other/`
- Indexes **never inline** → `index/` (one index per file, file named as the index).
- Triggers → `trigger/` (one per file).
- Packages: specs → `package_spec/`, bodies → `package_body/`.
- Object types: specs → `type_spec/`, bodies → `type_body/`.
- Views → `view/` (one per file).
- Sequences vs identity: Prefer identity columns for new tables unless an explicit requirement dictates sequences; keep legacy sequences if already in use.
- Header at top of every file:

