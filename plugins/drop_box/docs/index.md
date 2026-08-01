# Drop Box Documentation

Drop Box is Orac's bundled local-file ingestion adapter. It discovers and
normalises approved source documents while Orac Core owns managed content,
knowledge lineage, chunking, embeddings, authorisation, retrieval, and
grounding.

## Guides

- [Operator and APEX guide](drop-box.md): installation, the seeded
  `ORAC_DOCS` location, supported formats, App 10020 administration, service
  policy, testing, and troubleshooting.
- [Data lifecycle](drop-box-data-lifecycle.md): scanner observations,
  conversion, retries, Core handoff, source identity, database ownership, and
  failure behaviour.
- [Core document ingestion](../../../docs/document-ingestion.md): managed
  storage, Core worker settings, project scopes, RAG privileges, retrieval, and
  security boundaries.
- [General plugin lifecycle](../../../docs/plugins.md): manifests,
  installation, services, database deployment, APEX applications, and policy.

## Supplied Application

The plugin supplies `ORAC_DROPBOX_ADMIN` (application 10020) in workspace
`ORAC`, using parsing schema `ORAC_APX_PUB` and the `ORAC_ADMIN` role. Its
export is `plugins/drop_box/apex/f10020.sql`; the plugin installer deploys it
after the required plugin database objects and grants. Use App 1043 Plugin
Navigation to launch it and the operator guide to validate or troubleshoot it.
