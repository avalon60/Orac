# Orac APEX Agent Context

## Workspace and Parsing Schema

| Workspace | Parsing schema | Purpose |
| --- | --- | --- |
| `ORAC` | `ORAC_APX_PUB` | Core Orac administration and plugin-control applications |

The parsing schema is a least-privilege APEX access surface. Schema ownership,
grant direction, and database controller order remain owned by
`resources/db/schema/AGENT_CONTEXT.md`.

## Core Application and Export Mapping

| Application | Application ID | Export path | Ownership |
| --- | --- | --- | --- |
| Orac Administration | `1042` | `resources/db/apex/orac_apps/f1042.sql` | Core Orac |
| Plugin Control | `1043` | `resources/db/apex/orac_apps/f1043.sql` | Core Orac |
| Plugin App Scaffold | `10042` | `resources/db/apex/orac_apps/f10042.sql` | Core scaffold |

Treat the export metadata inside each file as corroborating identity evidence.
Do not allocate or renumber an application ID from the filename alone.

## Docker and Import Entrypoints

- `resources/docker/oracle/Dockerfile` copies `resources/db/apex` into the
  database image build context.
- `resources/docker/oracle/setup/045-orac-apex-import.sh` owns core workspace
  and application import sequencing.
- Preserve workspace provisioning, parsing-schema association, and application
  import order when changing either entrypoint.

## Navigation, Theme, and Plugin Boundaries

- Preserve each core application's established navigation, theme,
  authentication, authorisation, and shared-component boundaries.
- Plugin-owned APEX exports remain under `plugins/<plugin-code>/apex/` and are
  governed by root context plus the applicable plugin manifest.
- Do not move plugin exports into this core area or treat a plugin application
  ID as available for core allocation.

## Validation

Verify export application IDs and workspace metadata, inspect the Docker copy
and `045-orac-apex-import.sh` ordering, and use the repository's documented
Oracle/APEX installation checks after import-affecting changes.
