# Drop Box Plugin

`drop_box` is a generic source adapter for files dropped into configured
filesystem locations. A drop location is a watched folder plus routing metadata:
target scope, named processing profile, allowed file types, size limits,
stability interval, ignore patterns, and processing instructions.

Phase 1 scans enabled locations, waits until candidate files are stable,
calculates a SHA-256 hash, and creates queued jobs in `ORAC_DROPBOX`. It does not
move files, delete files, run OCR, convert documents to markdown, summarise,
chunk, embed, or write to a knowledge store.

## Capabilities

- Scans configured filesystem folders on a schedule.
- Supports recursive and non-recursive locations.
- Filters by extension, size, symlink status, missing paths, and ignore patterns.
- Skips common temporary, partial, and hidden files by default.
- Waits for stable size and mtime before hashing.
- Skips hashing when an unchanged observation is already queued.
- Re-stats after hashing and defers enqueue if the file changed while hashing.
- Creates durable jobs and audit events in the plugin-owned `ORAC_DROPBOX`
  schema.
- Provides an admin-only APEX app for location configuration and job inspection.

## Runtime

The plugin is a service-only plugin. It uses an automatic start policy so a
restart starts scanning after install once drop locations are enabled. When
started, `run_on_start` is enabled, so Orac runs one scan immediately and then
repeats on the configured 30-second schedule.

The scanner prevents overlapping ticks in the same process. It also skips
hashing when a job already exists for the same location, source path, source
size, and source mtime. After hashing, the scanner checks the file metadata
again; if size or mtime changed, no job is enqueued on that tick.

## Drop Location Configuration

Drop locations are stored in `orac_dropbox.drop_location` and should normally be
managed through the Drop Box admin APEX app.

Important columns:

- `location_code`: stable uppercase code for the location.
- `display_name`: admin-facing label.
- `path`: filesystem directory to scan.
- `target_scope_type` and `target_scope_key`: future document ingestion target.
- `processing_profile`: named ingestion recipe selected from
  `drop_processing_profile`.
- `processing_instruction`: extra location-specific guidance copied onto each
  job at enqueue time.
- `allowed_extensions`: comma-separated extensions, blank for all files.
- `recursive_yn`: whether to scan subdirectories.
- `ignore_patterns`: comma-separated glob patterns for temporary files.
- `move_processed_yn` and `processed_path`: stored for future processed-file
  movement. The switch governs only `processed_path`.
- `failed_path`: stored independently for future failed/quarantined-file
  handling.
- `max_file_size_mb`: optional size limit.
- `stability_seconds`: unchanged size and mtime interval required before hash.

The admin API performs configuration sanity checks before a location can be
enabled: location code format, active processing profile lookup, target scope
type/key, Y/N flags, positive stability and file-size values, a non-empty
absolute source path, and duplicate active source paths. Phase 1 does not
enforce a configured allowed root directory because no project-wide drop-box
base-directory concept exists yet. The scanner still performs runtime
filesystem validation for existence, permissions, symlinks, file stability, and
hashing safety before enqueueing jobs.

Default ignore handling excludes hidden dotfiles and common partial files such
as `*.tmp`, `*.part`, `*.partial`, `*.crdownload`, `.~*`, `~$*`, and `.DS_Store`.

## Processing Profiles

A processing profile is a named ingestion recipe. It gives future ingestion
workers a stable, shared instruction for how to interpret a queued source file.
The Drop Box admin app lists active profiles from
`orac_dropbox.drop_processing_profile_lov_v`; operators choose the friendly
profile name and the app stores the returned `profile_code`.

Seeded system profiles:

- `raw_reference`: preserve the source as reference material with original
  facts, terminology, meaning, and provenance.
- `concise_knowledge_note`: create a short reusable note with durable facts,
  operational guidance, caveats, and context.
- `implementation_decision_record`: extract problem, decision, rationale,
  consequences, alternatives where present, risks, and follow-up work.
- `technical_manual`: organise the source into procedural or reference
  documentation for engineers and operators.
- `troubleshooting_note`: capture symptoms, likely causes, diagnostics, fixes,
  verification steps, and limits.
- `automation_rule_note`: capture automation triggers, conditions, actions,
  safety constraints, failure handling, and expected outcomes.

Phase 1 does not run the recipe. It stores deterministic job snapshots:

- `effective_processing_profile`: selected recipe code at enqueue time.
- `effective_profile_instruction`: selected recipe text at enqueue time.
- `effective_instruction`: location-specific operator instruction at enqueue
  time.

Because the profile instruction is copied onto `drop_job`, changing a profile
definition later does not change the recipe text attached to already queued
jobs.

## Admin App

The plugin supplies the `ORAC_DROPBOX_ADMIN` APEX app:

- Application ID: `10020`.
- Workspace: `ORAC`.
- Parsing schema: `ORAC_APX_PUB`.
- Required role: `ORAC_ADMIN`.
- Installed through the plugin APEX app mechanism.

The app provides:

- A locations report with create, edit, view jobs, enable, and disable actions.
- A create/edit form for drop location settings.
- A plugin target LOV backed by `ORAC_CODE.PLUGIN_LOV_V`, which only lists
  enabled runtime-ready plugins.
- Free-text project target entry because there is no project metadata catalogue
  yet.
- A processing profile LOV backed by
  `ORAC_DROPBOX.DROP_PROCESSING_PROFILE_LOV_V`.
- A location detail page with current configuration and recent jobs.
- A read-only job detail page with source metadata, status, downstream document
  id, error message, and job event history.

All admin writes go through `ORAC_DROPBOX.DROP_BOX_ADMIN_API`. The APEX app reads
approved admin views and does not perform direct DML against `ORAC_DROPBOX`
tables.

## Database Interfaces

Runtime scanner access:

- `drop_location_runtime_v`: enabled scanner configuration.
- `drop_location_config_error_v`: enabled locations omitted from scanning
  because their processing profile is unknown or inactive.
- `drop_box_api.observation_exists`: unchanged-file pre-check.
- `drop_box_api.enqueue_job`: creates queued jobs.
- `drop_box_api.update_status`: records Core handoff success/failure.
- `drop_job_handoff_v`: queued or retryable jobs ready for Core managed-file
  capture.
- `drop_processing_profile_runtime_v`: active profile definitions.

Admin access:

- `drop_location_admin_v`: editable location configuration projection.
- `drop_processing_profile_lov_v`: active profiles for APEX select lists.
- `drop_processing_profile_admin_v`: all profile definitions for admin
  inspection.
- `drop_location_summary_admin_v`: Page 1 report summary including total and
  recent job counts, latest status, last processed timestamp, and example
  labels.
- `drop_job_admin_v`: recent job inspection.
- `drop_job_event_admin_v`: job audit history.
- `drop_box_admin_api`: create, update, enable, and disable locations with
  optimistic row-version checks.

## Job Creation

Python passes only observed file metadata and the drop location id to
`drop_box_api.enqueue_job`: source path, filename, size, mtime, stable timestamp,
and SHA-256 hash. The package copies target scope and the location-specific
processing instruction from `drop_location` onto `drop_job` at enqueue time. It
also joins the selected active profile and snapshots the profile code plus
profile default instruction onto the job.

Jobs are unique by `(drop_location_id, source_path, source_size_bytes,
source_mtime)`. The duplicate pre-check avoids hashing unchanged files; the
unique constraint protects the database if two enqueue attempts race.

Enabled locations that reference inactive legacy profiles are omitted from
`drop_location_runtime_v`. The service logs a configuration warning from
`drop_location_config_error_v`; no job event can be persisted for that skip in
Phase 1 because `drop_job_event` requires an existing `drop_job_id`.

## Core Managed-File Handoff

Drop Box owns filesystem discovery only. After enqueueing stable jobs it calls
`orac_core.knowledge.capture.KnowledgeManagedFileCaptureService`, passing the
trusted Drop Box job id, configured location root, source path, source hash,
source size, scope, profile, and instruction.

Core source identity is derived from the configured location code plus the
canonical relative POSIX path under that location root:
`<location_code>:<canonical-relative-posix-path>`. The persisted
`source_reference` is `drop_box:source:<sha256(source_key)>`; the readable
`source_key` is stored as the parent source reference. The identity deliberately
excludes absolute host paths.

Changed content at the same `source_key` creates a new document revision for
the same document. A rename or move changes the relative path and therefore
creates a new source/document identity. Moving the location root while
preserving the same `location_code` and relative path preserves identity;
changing `location_code` creates a new identity. Legacy `drop_box:drop_job:<id>`
sources may be re-keyed only by Core when exactly one matching legacy source is
found for the same source path and target scope, no stable-reference collision
exists, and the transactional update records an ingestion event. Ambiguous
legacy cases are refused.

The Core capture service validates that the source resolves under the configured
Drop Box root, rejects unsupported file types, oversized files, hash mismatches,
symlink escapes, and non-UTF-8 `.txt`/`.md` payloads, then copies to a temporary
file under the Core managed content root. It verifies SHA-256 before atomically
renaming into the content-addressed `sha256/ab/cd/<full-sha256>` path and only
then calls `orac_code.knowledge_ingestion_api.submit_managed_file`.

Failure boundary:

- Capture failure before rename removes the temporary file through the common
  cleanup path. No Core database request is created, and the Drop Box job is
  marked failed for retry.
- Duplicate payload reuse, validation failure, database failure, embedding
  failure, and cancellation all use the same temporary-file cleanup path. Core
  retains files only after they have been promoted into the content-addressed
  managed store and are explicitly available for retry.
- Rename success followed by database registration failure may leave an orphaned
  content-addressed file. Retry verifies the same file and hash before retrying
  registration; the job is not marked successful.
- A Drop Box job is marked `handed_off` only after Core returns an ingestion
  request id. The Core ingestion feature owns that request id.
- If a later Core worker sees a database request whose managed payload is
  missing, it marks the request failed with a missing-payload error and does not
  complete the request.

`drop_job.knowledge_ingestion_request_id` is deliberately not physically
present while the Core knowledge feature is paused. Plugin schemas must not
reference protected ORAC_CORE objects directly; the Core request itself owns the
physical foreign keys from source object through document, extraction, chunk,
and embedding rows.

## Examples

Only generic, disabled project examples are seeded automatically. Plugin-scoped
locations are not seeded blindly; create them through the Drop Box admin app
after the target plugin appears in the installed-plugin LOV.

Home Assistant conclusions example, not seeded automatically:

```text
location_code: HA_CONCLUSIONS
enabled_yn: N
path: /tmp/orac-dropbox-examples/home_assistant_conclusions
target_scope_type: plugin
target_scope_key: home_assistant
processing_profile: concise_knowledge_note
```

Seeded disabled project example:

```text
location_code: ORAC_ARCHITECTURE_NOTES
enabled_yn: N
path: /tmp/orac-dropbox-examples/orac_architecture_notes
target_scope_type: project
target_scope_key: ORAC_CORE
processing_profile: implementation_decision_record
```

## Operator Guidance

1. Install the plugin and its APEX app.
2. Open `ORAC_DROPBOX_ADMIN` as an `ORAC_ADMIN` user.
3. Create or edit a drop location.
4. For a plugin target, choose an installed plugin from the LOV.
5. For a project target, enter the project code manually.
6. Set an absolute source path, stability interval, size limit, extensions, and
   ignore patterns.
7. Enable the location only after the filesystem mount and permissions are
   ready.
8. Leave the scanner service policy as `auto` for normal operation, or set it to
   `manual` or `disabled` from App 1043 or `bin/orac-plugin.sh` for diagnostic
   or paused operation. The first scan runs immediately because `run_on_start`
   is true.
9. Use the location and job detail pages to inspect queued jobs and audit
   events.

## Service Lifecycle

Orac core owns plugin service lifecycle. During Orac startup and plugin routing
refresh, the core `PluginServiceManager` registers installed service plugins,
checks their effective policy, acquires the database lease, starts `auto`
services, keeps heartbeats current, and releases leases during shutdown.

Drop Box declares one service: `(plugin_id, service_code) = (drop_box,
scanner)`. It defaults to `auto` after install, so it is visible in service
status and starts on the next Orac restart. Change startup policy through the
Plugin Service Status report in App 1043, or from the CLI:

```bash
bin/orac-plugin.sh service policy drop_box scanner manual
bin/orac-plugin.sh service policy drop_box scanner auto
bin/orac-plugin.sh service policy drop_box scanner disabled
```

Find the current `row_version`, policy, state, owner, lease, heartbeat, tick,
and last error through:

```sql
select service_id,
       effective_policy,
       current_state,
       owner_id,
       lease_expires_on,
       last_started_on,
       last_heartbeat_on,
       last_tick_on,
       last_error_message,
       row_version
  from orac_code.plugin_service_status_v
 where plugin_id = 'drop_box'
   and service_code = 'scanner';
```

After a database rebuild, install or reinstall the Drop Box plugin and restart
the Orac runtime before expecting the service to appear in the Plugin Apps
operations page. Installation restores the plugin registry and APEX metadata;
the restart runs plugin routing/service refresh and recreates the
`drop_box:scanner` lifecycle row in `orac_core.plugin_services`.

`bin/orac-plugin.sh service run drop_box` remains a foreground diagnostic
command only. It uses the same service implementation and database lease path
as Orac core, refuses disabled services, and refuses to run if another active
owner already holds the scanner lease.

## Testing Scanner Operation

Use a dedicated local inbox for the first scanner test. The path must be visible
from the Orac runtime filesystem namespace. If Orac is running in Docker, the
folder must exist inside the container or be bind-mounted into the container at
the same path configured in the Drop Box admin app.

1. Create the test folder:

   ```bash
   mkdir -p /tmp/orac-dropbox-test/inbox
   ```

2. In `ORAC_DROPBOX_ADMIN`, create or edit a drop location:

   ```text
   location_code: LOCAL_TEST
   display_name: Local Scanner Test
   path: /tmp/orac-dropbox-test/inbox
   enabled_yn: Y
   target_scope_type: project
   target_scope_key: ORAC_CORE
   processing_profile: raw_reference
   allowed_extensions: md,txt
   recursive_yn: N
   max_file_size_mb: 10
   stability_seconds: 10
   ```

3. For a diagnostic test, run the scanner service in the foreground from the
   Orac project root. Use Ctrl-C when finished, or give it a test duration. This
   is not the normal operational start path; normal automatic scanning is owned
   by Orac core when the `(drop_box, scanner)` policy is `auto`.

   ```bash
   bin/orac-plugin.sh service run drop_box
   bin/orac-plugin.sh service run drop_box --duration-seconds 90
   ```

4. Drop a test file into the inbox:

   ```bash
   printf '# Drop Box Scanner Test\n\nThis is a test document.\n' > /tmp/orac-dropbox-test/inbox/scanner-test.md
   ```

5. Wait longer than `stability_seconds` plus one scan interval. The bundled
   plugin schedule currently scans every 30 seconds, so the example above needs
   more than 40 seconds after the file is written.

6. Verify through APEX:

   - Open `ORAC_DROPBOX_ADMIN`.
   - Confirm `LOCAL_TEST` shows an increased job count.
   - Click `View Jobs`.
   - Confirm `scanner-test.md` appears as a queued job.
   - Open the job detail page.
   - Confirm hash, size, status, and timestamps are populated.
   - Confirm job event history shows the queued/enqueue activity.

7. Verify through SQL as a fallback:

   ```sql
   select location_code,
          display_name,
          enabled_yn,
          path
     from orac_dropbox.drop_location
    where location_code = 'LOCAL_TEST';

   select source_filename,
          status_code,
          source_hash,
          source_size_bytes,
          detected_on,
          stable_on,
          created_on
     from orac_dropbox.drop_job
    where source_filename = 'scanner-test.md'
    order by drop_job_id desc;

   select e.event_ts,
          e.event_type,
          e.event_message
     from orac_dropbox.drop_job_event e
     join orac_dropbox.drop_job j
       on j.drop_job_id = e.drop_job_id
    where j.source_filename = 'scanner-test.md'
    order by e.event_ts;
   ```

Troubleshooting checks:

- Confirm the drop location is enabled.
- Confirm the configured path exists from the Orac runtime perspective, not
  only from the host shell.
- If running in Docker, confirm the inbox is inside the container or
  bind-mounted into it.
- Check mount permissions for the runtime user.
- Check `allowed_extensions`, `max_file_size_mb`, and `ignore_patterns`.
- Confirm the file remains unchanged for `stability_seconds`.
- Check foreground service output or Orac plugin service logs.
- Check `drop_job_event_admin_v` or `drop_job_event` for persisted job errors.
- Confirm the source path is not a symlink if symlinks are blocked.

Phase 1 persists queued jobs and job events after enqueue/status updates. It
does not currently persist scanner-only skip observations such as missing paths,
ignored files, unstable files, disallowed extensions, too-large files, symlinks,
or most path/permission failures. Those appear in service statistics and logs.

## Testing With Project Docs

For a documentation-file test, copy one known Markdown file into the dedicated
test inbox. Do not point the scanner at the whole `docs` directory for first
testing; recursive scanning, duplicate behavior, and file type filters should be
understood before scanning broad project folders.

```bash
cp docs/agent-guardrails/50-plugin-standards.md /tmp/orac-dropbox-test/inbox/plugin-standards.md
```

After the next stable scan, verify that `plugin-standards.md` appears as a
handed-off drop job with job event history. Drop Box still does not convert, summarise, chunk, embed, move files, delete, or quarantine files; those responsibilities belong to Core ingestion.

## Future Extensions

File-level directives, email ingestion, post-processing file movement, and
delegated plugin administration are explicitly deferred.
