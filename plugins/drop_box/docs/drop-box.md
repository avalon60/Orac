# Drop Box

The Drop Box plugin watches configured local folders, validates stable files,
converts supported sources to canonical Markdown, and hands them to Orac Core
for durable knowledge ingestion.

This guide is for administrators and operators. The
[Drop Box data lifecycle](drop-box-data-lifecycle.md) describes the internal
job and handoff model. Core ownership, worker settings, and App 1042
configuration are documented in
[Document Ingestion](../../../docs/document-ingestion.md).

## Current Capabilities

Drop Box currently:

- scans enabled folders every 30 seconds and once when the service starts;
- supports recursive and non-recursive locations;
- filters by extension, size, ignore pattern, symlink status, and stability;
- hashes stable sources with SHA-256 and deduplicates unchanged observations;
- stores jobs and job events in the plugin-owned `ORAC_DROPBOX` schema;
- normalises Markdown and UTF-8 plain text without Pandoc;
- converts DOCX, HTML, ODT, RTF, and EPUB with an allowlisted Pandoc recipe;
- submits the original source, canonical Markdown, extraction provenance,
  classification tags, and ingestion notes to Core;
- reports Drop Box and Core lifecycle state through its APEX application.

It does not ingest PDF, OCR output, spreadsheets, presentations, remote
content, or embedded media. It does not move, delete, or quarantine source
files after processing.

## Install and Open the Application

Install the bundled plugin from the Orac project root:

```bash
bin/orac-plugin.sh install --bundled drop_box
bin/orac-plugin.sh check drop_box
```

Restart or refresh the Orac runtime after installation so the managed service
registry contains the scanner:

```bash
bin/orac-ctl.sh restart
```

The plugin supplies:

| Setting | Value |
| --- | --- |
| Application | `ORAC_DROPBOX_ADMIN` |
| Application ID | `10020` |
| Workspace | `ORAC` |
| Parsing schema | `ORAC_APX_PUB` |
| Required role | `ORAC_ADMIN` |

Open Orac Administration App 1042, select **Plugin Control**, and use App 1043
Page 2 **Plugin Navigation** to launch **Drop Box Admin**. If its card is not
visible, use App 1043 Pages 3/4 to confirm that the plugin APEX app is installed
successfully and enabled.

Installation imports the required APEX export. App 1043 app enablement controls
listing and launch; it does not install the plugin or start its scanner.

Plugin installation also provisions `ORAC_DROPBOX` and applies the catalogued
scope and tag validation grants before the plugin Liquibase changelog runs.
The core database installer does not create this optional schema. If `check`
reports a missing or invalid bridge dependency, verify the corresponding
`ORAC_PLUGIN` package in the core deployment and rerun plugin installation;
do not bypass the failure with a Liquibase `MARK_RAN` precondition.

## Core Prerequisites

Before creating a location:

1. Confirm `[knowledge].enabled = true` in `resources/config/orac.ini`.
2. For a project target other than the seeded `ORAC_CORE` project, register and
   activate the project in App 1042 Pages 37/38.
3. For a plugin target, install and enable the target plugin and ensure it is
   runtime-ready.
4. In App 1043 Page 1, leave the `drop_box` / `scanner` service policy as
   `auto` for normal operation.
5. If users will query the resulting corpus through dialogue, grant each
   principal the relevant canonical scope in App 1042 Pages 39/40. The shipped
   configuration enables `[knowledge.dialogue]`; confirm it has not been
   explicitly disabled.

A RAG usage grant is required for dialogue retrieval, not ingestion. It does
not make an unknown or inactive target eligible.

## Shipped ORAC_DOCS Location

The plugin database install seeds one reserved, enabled location for the
repository documentation:

| Setting | Seeded value |
| --- | --- |
| Location code | `ORAC_DOCS` |
| Source path | `${ORAC_HOME}/docs` |
| Target | `PROJECT:ORAC_CORE` |
| Extensions | `md` |
| Recursive | Yes |
| Classification | `RAW_REFERENCE` |
| Maximum size | 10 MiB |
| Stability | 10 seconds |

The scanner resolves `${ORAC_HOME}` from its runtime environment and falls back
to the established Orac project root. Other environment-variable tokens,
relative paths, control characters, and `..` traversal are rejected.
`pending_work/**` and `backlog/**` are excluded so draft plans and backlog
material do not enter the canonical corpus. Standard hidden, temporary, and
partial-file exclusions also apply.

`ORAC_DOCS` is seed-owned configuration. The adoption migration updates an
existing row with that code once; later administrator edits are preserved.
Installing the location does not grant any user dialogue access. Grant
`PROJECT:ORAC_CORE` separately in App 1042 Pages 39/40 when retrieval is
required.

## Pandoc Capability

Pandoc `>=3.1,<4` is an optional declared command prerequisite. Markdown and
plain text work without it. DOCX, HTML, ODT, RTF, and EPUB jobs wait in
`deferred_prerequisite` when Pandoc is missing, incompatible, or cannot be
probed.

Check the active plugin and the service environment:

```bash
bin/orac-plugin.sh check drop_box
pandoc --version
```

Orac probes a Core-owned command catalogue and never installs operating-system
packages. Installing a compatible Pandoc into the existing controlled service
path is detected by the 15-minute re-probe. A changed container image,
executable mount, or configured path requires the affected service or
container to restart.

The capability banner on Drop Box App 10020 Page 1 reports a bounded safe
status. It does not expose executable paths or raw probe output.

## APEX Page Guide

### Page 1: Drop Locations

Page 1 is the operational dashboard. It provides:

- create and edit actions;
- enable and disable actions;
- links to location details and activity;
- current source path, target, and stability configuration;
- a bounded Pandoc capability banner;
- mutually exclusive lifecycle counts.

The lifecycle buckets are:

| Bucket | Meaning |
| --- | --- |
| Awaiting Handoff | The Drop Box job is queued or processing before Core acceptance. |
| Prerequisite Deferred | A supported conversion is waiting for Pandoc readiness. |
| Conversion Retry | A retryable converter failure is waiting for its next attempt. |
| Core In Progress | Core accepted the request but has not made it searchable. |
| Searchable | Core completed the current request with searchable embedded chunks. |
| Failed / Attention | Drop Box failed/quarantined jobs, broken Core correlation, Core failure, or a completed request that is not searchable. |
| Skipped | Duplicate, disallowed, or oversized source observations persisted as skipped jobs. |

Each job contributes to exactly one bucket. **Failed / Attention** includes
historical and consistency conditions and does not by itself prove that an
incident is still active.

### Page 2: Drop Location Form

Page 2 opens as a resizable right-side drawer. The classification-tag shuttle
uses a full form row so that descriptive tag names remain visible.

Use Page 2 to create or edit a watched folder. Save through the form so the
approved admin API validates the configuration and canonical target.

#### Basic Details

| Field | Guidance |
| --- | --- |
| Location Code | Stable uppercase identity for the location. It contributes to document identity, so changing it creates new source identities. |
| Display Name | Short administrator-facing label. |
| Source Path | Absolute directory visible from the Orac runtime filesystem namespace, or `${ORAC_HOME}/` followed by an Orac-relative path. |
| Enabled | Disabled locations remain configured but are not scanned. Create a location disabled until its mount, permissions, and target are ready. |

If Orac runs in Docker, a host directory is not automatically visible inside
the container. Bind-mount it and configure the path as it appears to the Orac
runtime.

#### Target / Routing

| Field | Guidance |
| --- | --- |
| Target Scope Type | Choose `Project` for a registered project or `Plugin` for an installed eligible plugin. |
| Project Code | Select an active project created in App 1042 Pages 37/38. |
| Plugin Target | Select an enabled, installed, runtime-ready plugin scope. |
| Classification Tags | Choose one to ten active Core-owned descriptive tags. |

Target lists come from the canonical Core scope registry. A location does not
create its own project or plugin scope.

Classification tags are provenance. They do not select a converter, alter
chunking or embeddings, influence ranking or authorisation, enter privileged
prompts, or change routing.

#### Scanner Rules

| Field | Guidance |
| --- | --- |
| Allowed Extensions | Comma-separated extensions without leading dots. Use an explicit subset of `md,txt,docx,html,htm,odt,rtf,epub`. |
| Recursive Scan | Include regular files beneath subdirectories when enabled. |
| Ignore Patterns | Comma-separated glob patterns matched against names and relative paths. |
| Maximum File Size MB | Optional positive per-location limit. It can reduce but not exceed the hard 100 MiB capture limit. |
| Stable Seconds | Positive interval for which size and modification time must remain unchanged before hashing. |

Leaving **Allowed Extensions** blank permits all extensions through the cheap
scanner filter; unsupported formats will later become
`skipped_disallowed_type`. An explicit supported list is recommended.

Hidden dotfiles and common partial-file patterns are ignored by default,
including `*.tmp`, `*.part`, `*.partial`, `*.crdownload`, `.~*`, `~$*`, and
`.DS_Store`. Symlinks are not followed.

#### Ingestion Notes

Ingestion notes are optional provenance copied to each queued job. They are
untrusted data and are never executed or treated as model instructions. Keep
them concise; Core rejects notes larger than 16 KiB.

#### Post-processing / Future Use

`Move Processed`, `Processed Path`, and `Failed / Quarantine Path` are stored
future-use settings. The current service does not move, delete, or quarantine
files. Leave **Move Processed** disabled unless you are preserving intended
future configuration.

#### Delete

Delete is confirmation-protected and succeeds only when the location has no
job history. Disable a historical location instead of attempting to delete its
audit lineage.

### Pages 3 and 4: Location and Job Detail

Page 3 shows the current location configuration and recent jobs. Page 4 shows
one job's source metadata, state, safe reason code, downstream document
identifier, and event history.

The application renders bounded redacted errors. Review restricted service
logs for full diagnostics; raw converter output, stack traces, credentials,
ingestion notes, and unrestricted event payloads are not displayed.

### Page 5: Activity

Page 5 correlates each Drop Box job with its Core ingestion request. It keeps
the two lifecycles separate:

- Drop Box state and reason;
- Core request and stage;
- accepted, claimed, latest-event, and completion times;
- document and revision identifiers;
- chunk and embedded-chunk counts;
- final searchability.

Use **View Activity** on Page 1 to filter this report to one location.

## Supported Formats and Limits

| Extension | Handling | Pandoc required |
| --- | --- | --- |
| `.md` | UTF-8/BOM and newline normalisation; preserved as Markdown | No |
| `.txt` | UTF-8/BOM and newline normalisation; treated as canonical Markdown text | No |
| `.docx` | Archive/signature validation and fixed DOCX-to-GFM conversion | Yes |
| `.html`, `.htm` | UTF-8 and HTML marker validation, then fixed HTML-to-GFM conversion | Yes |
| `.odt` | Archive/signature validation and fixed ODT-to-GFM conversion | Yes |
| `.rtf` | RTF signature validation and fixed RTF-to-GFM conversion | Yes |
| `.epub` | Archive/signature validation and fixed EPUB-to-GFM conversion | Yes |

Hard limits include:

- 100 MiB original source;
- 50 MiB canonical Markdown;
- 60-second Pandoc conversion;
- 10,000 archive entries;
- 250 MiB expanded archive total;
- 100 MiB per expanded archive member;
- 200:1 compression ratio;
- 400 MiB temporary conversion directory.

Encrypted archives, archive traversal, archive symlinks, raw HTML output,
Pandoc filters/defaults, remote resources, and filename-derived command options
are rejected or disabled.

## Service Policy and Diagnostics

Normal operation uses App 1043 Page 1 with:

```text
plugin: drop_box
service: scanner
policy: auto
```

CLI equivalents are:

```bash
bin/orac-plugin.sh service status drop_box
bin/orac-plugin.sh service status drop_box scanner --require-running
bin/orac-plugin.sh service policy drop_box scanner auto
bin/orac-plugin.sh service policy drop_box scanner manual
bin/orac-plugin.sh service policy drop_box scanner disabled
```

Use `--require-running` in automation and rebuild checks. The command keeps the
normal JSON output and succeeds only when the matching service exists, its
state is `running`, and its database lease is active. Without the flag, status
remains observational and returns success after printing available rows.

`bin/orac-plugin.sh service run drop_box` is a foreground diagnostic, not the
normal startup path. It uses the managed service lease and refuses to run when
the policy is disabled or another active owner holds the scanner lease.

## First Ingestion Test

Use a dedicated directory rather than pointing the first test at a broad
document tree:

```bash
mkdir -p /tmp/orac-dropbox-test/inbox
```

Create an initially disabled project-targeted location:

```text
Location Code: LOCAL_TEST
Display Name: Local Scanner Test
Source Path: /tmp/orac-dropbox-test/inbox
Enabled: No
Target Scope Type: Project
Project Code: ORAC_CORE
Classification Tags: RAW_REFERENCE
Allowed Extensions: md,txt
Recursive Scan: No
Maximum File Size MB: 10
Stable Seconds: 10
```

Verify the path from the Orac runtime, then enable the location and create a
test file:

```bash
printf '# Drop Box Scanner Test\n\nThis is a test document.\n' \
  > /tmp/orac-dropbox-test/inbox/scanner-test.md
```

Wait longer than the stability interval plus the 30-second scan interval. Then:

1. Confirm the Page 1 job count increases.
2. Open **View Activity** and find `scanner-test.md`.
3. Verify the Drop Box state reaches `handed_off`.
4. Verify a Core request identifier appears.
5. Confirm Core reaches `COMPLETED`, `Searchable` is `Y`, and chunk and
   embedding counts agree.
6. Open the job detail and review its safe event history.

For a documentation test, copy one known Markdown file rather than scanning the
whole repository:

```bash
cp docs/agent-guardrails/50-plugin-standards.md \
  /tmp/orac-dropbox-test/inbox/plugin-standards.md
```

## Troubleshooting

### Location Is Not Scanned

- Confirm the location and scanner service are enabled.
- Confirm the source path exists in the Orac runtime namespace.
- Check container bind mounts and runtime-user permissions.
- Check the active target scope, classification tags, legacy compatibility
  profile, allowed extensions, size limit, and ignore patterns.
- Confirm the file remains unchanged for the configured stability interval.
- Confirm the source is a regular file and not a symlink.

Scanner-only observations such as missing paths, ignored files, unstable files,
disallowed extensions before enqueue, oversized files, symlinks, and many
permission errors are reported in service statistics/logs rather than as job
events because no job exists yet.

### Office or Web Files Are Deferred

- Check the Page 1 capability banner.
- Run `bin/orac-plugin.sh check drop_box`.
- Verify a compatible Pandoc is visible to the service runtime.
- Restart the affected service/container if its executable path or image
  changed.
- Do not repeatedly edit the source merely to trigger a probe; prerequisite
  deferral is rechecked without consuming conversion attempts.

### Conversion Retry or Failure

Converter failures wait one minute and then five minutes; the third attempted
conversion becomes terminally failed. Unsafe or invalid input is quarantined
without retry. Correct the source and create a new source observation; there is
no unreviewed manual terminal-job requeue action.

### Core Does Not Complete

- Confirm `[knowledge].enabled` and the `orac_core` /
  `knowledge_ingestion` service state.
- Confirm the target remains active and eligible.
- Compare Drop Box and Core state on Page 5.
- Check for missing managed payload, hash mismatch, empty canonical content,
  worker retry, or embedding failure in restricted logs.
- `ORA-20429` means Core found an existing document version with the same
  content hash, but one or more immutable metadata fields differ. The warning
  lists only the conflicting field names in deterministic order; it does not
  log their values. A common `source_modified_on` conflict occurs when a file
  is touched or regenerated without changing its content. The Drop Box job
  remains queued under the existing retry policy, so the warning will recur
  until the observation and existing lineage are reconciled through an
  authorised recovery workflow.
- Run `bin/orac-knowledge.sh reconcile` for a bounded read-only comparison of
  database lineage and managed-store state. `BLOCKED` identifies durable
  divergence; `INCOMPLETE` means the scan must be safely retried.
- Do not grant broad schema access or use direct table DML to repair the
  lifecycle.
- Do not delete, register, quarantine, rewrite, or recover managed content to
  make a test or reconciliation report pass. Those actions require a separate
  authorised recovery workflow that is not supplied by Drop Box.
