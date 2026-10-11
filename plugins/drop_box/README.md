# Drop Box Plugin

`drop_box` is Orac's bundled local-file ingestion adapter. It watches
configured filesystem locations, validates stable source files, creates durable
plugin-owned jobs, and produces canonical Markdown for Core knowledge
ingestion.

Drop Box owns discovery, format validation, native normalisation, and controlled
Pandoc conversion. Orac Core owns content-addressed originals, transactional
knowledge records, document versions, structure-aware chunks, embeddings,
relational classification tags, retrieval, and grounding provenance.

## Documentation

- [Drop Box documentation index](docs/index.md): entry point for plugin users
  and maintainers.
- [Drop Box operator and APEX guide](docs/drop-box.md): installation,
  supported formats, App 10020 configuration, service policy, testing, and
  troubleshooting.
- [Drop Box data lifecycle](docs/drop-box-data-lifecycle.md): scanner,
  conversion, retry, handoff, source identity, database boundaries, and Core
  worker behaviour.
- [Core document ingestion](../../docs/document-ingestion.md): Core settings,
  managed storage, App 1042/1043 configuration, RAG privileges, security, and
  retrieval boundaries.
- [General plugin lifecycle](../../docs/plugins.md): installation, manifests,
  services, APEX apps, prerequisites, and plugin policy.

## Capability Summary

- Native Markdown and UTF-8 plain-text canonicalisation.
- Text-based PDF extraction through optional Poppler `pdftotext`.
- DOCX, HTML, ODT, RTF, and EPUB conversion through optional Pandoc
  `>=3.1,<4`.
- Recursive or non-recursive filesystem scanning with extension, size,
  stability, ignore-pattern, and symlink controls.
- Durable jobs, retry metadata, and redacted audit events in `ORAC_DROPBOX`.
- Project or plugin target scopes selected from the Core registry.
- One to ten Core-owned descriptive classification tags.
- Admin-only APEX application `ORAC_DROPBOX_ADMIN` (App 10020).
- Seeded recursive `ORAC_DOCS` location targeting `PROJECT:ORAC_CORE`.

OCR for scanned PDFs, spreadsheets, presentations, remote acquisition, embedded-media
extraction, source-file movement, deletion, and physical quarantine are not
implemented.

## Runtime and Package Identity

The source manifest is [`plugins/drop_box.json`](../drop_box.json). It declares:

- plugin id `drop_box`;
- scheduled service `scanner`;
- automatic startup and a 30-second interval;
- optional Pandoc and Poppler command prerequisites;
- plugin-owned schema `ORAC_DROPBOX`;
- approved `ORAC_PLUGIN` scope and tag validation bridge dependencies;
- required APEX application `ORAC_DROPBOX_ADMIN`.

The installed runtime uses the managed plugin snapshot under
`$ORAC_HOME/var/plugins/installed/`; changing this source directory does not
update an installed snapshot until the plugin is installed again.

Install and validate the bundled plugin with:

```bash
bin/orac-plugin.sh install --bundled drop_box
bin/orac-plugin.sh check drop_box
```

Use App 1043 **Plugin Control** for normal service policy and application
launch. The CLI foreground service is a diagnostic path:

```bash
bin/orac-plugin.sh service run drop_box --duration-seconds 90
```

Do not use direct table DML to configure locations or repair jobs. App 10020
writes through `orac_dropbox.drop_box_admin_api`, and runtime handoff crosses
the plugin boundary only through approved Core interfaces.

The core database deployment does not create `ORAC_DROPBOX` or grant to it.
Plugin installation provisions the schema, applies the two catalogued bridge
grants, and then deploys the plugin changelog. If installation reports a
missing bridge API, repair or redeploy the core database before retrying the
plugin; do not mark the grant as ran or add the optional schema to a core
changelog.
