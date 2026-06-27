# Drop Box Plugin

`drop_box` is a generic source adapter for files dropped into configured
filesystem locations. The folder is deliberately dumb: the database
configuration for each drop location defines the target scope, processing
profile, allowed file types, size limits, stability interval, and processing
instructions.

Phase 1 scans enabled locations, waits until candidate files are stable,
calculates a SHA-256 hash, and creates queued jobs in `ORAC_DROPBOX`. It does not
move files, delete files, run OCR, convert documents to markdown, summarise,
chunk, embed, or write to a knowledge store.

## Runtime

The plugin is a service-only plugin. It uses a manual start policy so operators
can configure mounts and drop locations before scanning begins. When started,
`run_on_start` is enabled, so Orac runs one scan immediately and then repeats on
the configured schedule.

The scanner skips overlapping ticks in the same process. It also skips hashing
when a job already exists for the same location, source path, source size, and
source mtime.

## Drop Location Configuration

Drop locations are stored in `orac_dropbox.drop_location`.

Important columns:

- `location_code`: stable uppercase code for the location.
- `path`: filesystem directory to scan.
- `target_scope_type` and `target_scope_key`: future document ingestion target.
- `processing_profile`: processing style for the future ingestion pipeline.
- `processing_instruction`: copied onto each job at enqueue time.
- `allowed_extensions`: comma-separated extensions, blank for all files.
- `recursive_yn`: whether to scan subdirectories.
- `ignore_patterns`: comma-separated glob patterns for temporary files.
- `max_file_size_mb`: optional size limit.
- `stability_seconds`: unchanged size and mtime interval required before hash.

The admin API performs configuration sanity checks before a location can be
enabled: location and profile code formats, target scope type/key, Y/N flags,
positive stability and file-size values, a non-empty absolute source path, and
duplicate active source paths. Phase 1 does not enforce a configured allowed
root directory because no project-wide drop-box base-directory concept exists
yet. The scanner still performs runtime filesystem validation for existence,
permissions, symlinks, file stability, and hashing safety before enqueueing
jobs.

Default ignore handling excludes hidden dotfiles and common partial files such
as `*.tmp`, `*.part`, `*.partial`, `*.crdownload`, `.~*`, `~$*`, and `.DS_Store`.

## Examples

Home Assistant conclusions:

```text
location_code: HA_CONCLUSIONS
enabled_yn: N
path: /__orac_dropbox_examples__/home_assistant_conclusions
target_scope_type: plugin
target_scope_key: home_assistant
processing_profile: concise_knowledge_note
```

Orac architecture notes:

```text
location_code: ORAC_ARCHITECTURE_NOTES
enabled_yn: N
path: /__orac_dropbox_examples__/orac_architecture_notes
target_scope_type: project
target_scope_key: ORAC_CORE
processing_profile: implementation_decision_record
```

## Future Extensions

Future phases can consume `drop_job_handoff_v`, convert source material to
canonical markdown, optionally synthesise notes, chunk, embed, and persist into
the retrieval store through approved Orac interfaces. File-level directives,
email ingestion, post-processing file movement, and delegated plugin
administration are explicitly deferred.
