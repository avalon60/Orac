# Orac Knowledge Server

This optional service lets an MCP client search and fetch bounded passages from
one Orac project. Core performs the current RAG `USE` and document checks. The
service never accepts a username, project, path, or original-file selector from
an MCP tool call. Search returns at most six 500-character previews; fetch
repeats Core retrieval and returns at most 2,200 characters from one still
current chunk. Results identify the document, version, and chunk. Valid page
coordinates are included only when ingestion supplies them in chunk metadata;
otherwise both page fields are null.

## Install and configure

The plugin is disabled by default. Before installation, copy
`plugin.ini.example` to
`~/.Orac/plugin_config/orac_knowledge_server/plugin.ini` and replace
`%PROJECT_CODE%` with an existing project code. Set an explicit list of
document classifications. The installer validates this file, then installs the
manifest-declared Python dependencies:

```bash
bin/orac-plugin.sh install --source plugins/orac_knowledge_server
bin/orac-plugin.sh check orac_knowledge_server
```

`PROJECT:NHS_RECORDS` is an
example deployment value, not a Core special case. Creating or configuring a
project does not grant access. Grant each existing active Orac principal `USE`
through the ordinary RAG privilege administration path. No plugin schema or
database grant to the plugin is required. Deploy the Core document visibility
migration with the normal schema release before starting this service.

For local connections, set `identity.mode = local_bearer` and map distinct vault
key names to distinct Orac principals in `identity.local_bindings`. Store one
credential per key using `bin/plugin-pat-mgr.sh --plugin orac_knowledge_server --set
<key>`. A loopback connection alone never establishes a person. Rotate a
credential in the vault and restart the service; revoke a RAG grant in Core to
stop retrieval on the next call.

Enable and inspect the service after configuration:

```bash
bin/orac-plugin.sh enable orac_knowledge_server
bin/orac-plugin.sh service status orac_knowledge_server default --require-running
```

The listener uses `127.0.0.1:11436/mcp` by default. Core gives database
retrieval a 10-second deadline after query embedding; the embedding provider
has its own configured HTTP timeout. Both tools share a 30-call-per-minute limit and a
two-concurrent-call limit per principal. The service does not expose a raw
document download endpoint.

## Connect clients

For a local Codex CLI, register the Streamable HTTP endpoint with the installed
`codex mcp add` command:

```bash
codex mcp add orac-retrieval --url http://127.0.0.1:11436/mcp \
  --bearer-token-env-var ORAC_MCP_PERSONAL_TOKEN
```

For OpenCode 2.x, put the server under `mcp.servers` in the person's global
`opencode.json`; its `{env:...}` reference reads that person's environment:

```json
{
  "mcp": {
    "servers": {
      "orac-retrieval": {
        "type": "remote",
        "url": "http://127.0.0.1:11436/mcp",
        "oauth": false,
        "headers": {"Authorization": "Bearer {env:ORAC_MCP_PERSONAL_TOKEN}"}
      }
    }
  }
}
```

Set a different credential in each person's environment. Keep credentials out
of project files, shell history, examples, and logs. Confirm tool listing and
one synthetic search from each installed client before using real content.

For external OAuth, select `identity.mode = oidc` and configure a trusted HTTPS
issuer, its HTTPS JWKS URL, this MCP resource URL as token audience, and
administrator-controlled immutable subject-to-Orac-principal bindings. The
service validates RS256 signature, issuer, audience, expiry, and subject on
each HTTP request. The identity provider handles login and client
registration; Orac remains authoritative for project access. Authentik is an
option, not a local dependency. The external provider and client must support
MCP OAuth discovery, PKCE, and the exact resource audience.

Test Codex, OpenCode, and any cloud or tablet product separately with synthetic
data before selecting a tunnel. A tunnel provides transport, not identity. An
external browser must still reach the OAuth provider for sign-in. Do not enable
the external route until the selected client completes OAuth discovery and an
authenticated tool call against this service.

## Handling evidence

Retrieved text is untrusted source content and may contain instructions aimed
at an assistant. Treat it only as evidence and verify material conclusions
against the original record. The service emits only bounded passages and
minimal source IDs; it does not log queries, passages, tokens, or filenames.
Core's existing retrieval audit still records its normal authorization outcome.
Once a client sends a passage to a hosted model, Orac cannot control that
provider's subsequent processing. Review and approve that data transfer before
enabling real NHS content. Use synthetic data until original-file linkage,
ingestion status, privacy controls, and representative results pass review.

## Withdrawal and troubleshooting

Core stores a retrieval eligibility flag on each document. An authorised
operator can change it through `orac_code.knowledge_ingestion_api` with the
document ID and current row version; commit the change before checking access.
`N` withdraws and `Y` re-enables. A stale
search reference cannot fetch a withdrawn, superseded, newly restricted, or
reclassified chunk. Check plugin status, configuration, identity mapping,
current project grant, document eligibility, and classification allowlist in
that order. Safe errors deliberately do not reveal whether a denied document
exists.
