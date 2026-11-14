# Orac Knowledge Server

This optional service lets an authenticated MCP client discover currently
authorised Orac projects, then search and fetch bounded passages from one or
all of them. Core performs current RAG `USE` and document checks. The service
never accepts a username, permission claim, path, or original-file selector
from an MCP tool call. `list_projects` returns up to 25 project codes, display
names, and descriptions per page with a `next_offset` for the next call. Each
page is read from the current authorised catalogue. Search accepts an optional
`project_code`; omitting it searches across authorised projects. Search returns
at most six 500-character previews; fetch repeats Core retrieval and returns
at most 2,200 characters from one still current chunk. Results identify the
project, document, version, and chunk. Valid page
coordinates are included only when ingestion supplies them in chunk metadata;
otherwise both page fields are null.

## Install and configure

The plugin is disabled by default. Before installation, copy
`plugin.ini.example` to
`~/.Orac/plugin_config/orac_knowledge_server/plugin.ini`. Set an explicit list
of document classifications. Omit `retrieval.project_code` to allow discovery
and search across the connected user's currently authorised projects, or set
it to one existing project code as an administrator restriction. A present but
blank or invalid code is rejected. Existing single-project configurations keep
their restriction. The installer validates this file, then installs the
manifest-declared Python dependencies:

```bash
bin/orac-plugin.sh install --source plugins/orac_knowledge_server
bin/orac-plugin.sh check orac_knowledge_server
```

`NHS_RECORDS` is an example project code, not a Core special case. Creating or
configuring a project does not grant access. Grant each existing active Orac principal `USE`
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
has its own configured HTTP timeout. All three tools share a 30-call-per-minute
limit and a two-concurrent-call limit per principal. The service does not expose a raw
document download endpoint. A catalogue above 4,096 authorised projects fails
closed instead of returning a partial list.

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

## Ask a client to search

To explicitly request a search in a connected Codex session, try:

> Use the `orac-retrieval` MCP server. Call `list_projects` to confirm that I
> can access the `CHESS` project. Then call `search` with
> `project_code: "CHESS"` to find the moves associated with the Ruy Lopez
> opening. Fetch the most relevant references before answering, and identify
> the supporting document and version. If the project or evidence is
> unavailable, say so.

`CHESS` is an example project code. Replace it with the code returned by
`list_projects`; the connected principal needs current `USE` access, and any
administrator `retrieval.project_code` restriction must permit it. The server
searches the project's indexed evidence, so the response depends on what has
been ingested and remains retrievable.

An optional project-specific Codex skill could encourage the same workflow
when chess is the subject of a user's turn. For example, its skill description
could say: “Use when the user's request is about chess; search the authorised
CHESS Orac project for relevant evidence before answering.” Its instructions
would call `list_projects` if needed, then `search` with `project_code: "CHESS"`,
and `fetch` promising references. Skill matching is model-guided rather than
an exact keyword trigger, so this does not guarantee a search every time the
word “chess” appears. Explicitly invoking the skill or requesting the MCP
search is the reliable way to ask for one. A skill cannot grant project access.

## Handling evidence

Project codes, display names, and descriptions are disclosed to connected MCP
clients through `list_projects`. The authenticated principal and current Core
`USE` grants control the catalogue; an administrator project restriction can
narrow it further. A previous discovery result never grants search or fetch
access. Core checks the selected project on every search and checks the
reference's project again on fetch. Clients may send project metadata or
passages to a hosted model, so review that disclosure before enabling real data.

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
current project grant, optional administrator restriction, document eligibility,
and classification allowlist in
that order. Safe errors deliberately do not reveal whether a denied document
exists.
