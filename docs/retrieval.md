# Internet Retrieval

Orac treats internet retrieval as core, policy-controlled runtime plumbing.
Search results and fetched pages are untrusted evidence, never instructions.

## Retrieval Modes

The `[retrieval]` section controls when online evidence may be requested:

| Mode | Behaviour |
|---|---|
| `disabled` | Do not perform internet retrieval. |
| `explicit_only` | Search only when the user explicitly asks for current or online information. |
| `suggest_search` | Ask before searching when freshness is detected. |
| `auto_safe` | Search automatically for high-confidence current-information requests. |

The shipped mode is `explicit_only`. In that mode, merely asking about a topic
that may be current does not promise an automatic web search. Direct commands
such as `Search the web for ...` select the internet route before plugin
interception, but still pass through this policy and can be refused when
retrieval is disabled.

## SearXNG

SearXNG is the current local/private search provider. Orac calls:

```text
<base_url>/search?q=<query>&format=json
```

The shipped endpoint is `http://127.0.0.1:8888`. Retrieval requires SearXNG
when `internet_search_enabled = true` and `default_search_provider = searxng`.

```ini
[retrieval]
internet_search_enabled = true
internet_search_mode = explicit_only
default_search_provider = searxng
max_search_results = 5
max_sources_to_fetch = 3
max_response_bytes = 256000
max_redirects = 3
cache_ttl_hours = 12
require_citations = true
retrieval_response_style = normal

[retrieval.searxng]
base_url = http://127.0.0.1:8888
autostart = true
host = 127.0.0.1
port = 8888
timeout_seconds = 10
```

## Start and Test SearXNG

With `autostart = true`, `bin/orac-ctl.sh` activates the Compose `search`
profile.

```bash
bin/orac-ctl.sh compose-check
bin/orac-ctl.sh start
curl 'http://127.0.0.1:8888/search?q=Neil%20Armstrong&format=json'
```

The response should be JSON containing a `results` array.

```bash
bin/orac-ctl.sh logs search
bin/orac-ctl.sh status
```

The Compose service mounts
`resources/docker/oracle/searxng/settings.yml`. That file must enable both
`html` and `json` search formats. Without JSON format support, the endpoint used
by Orac returns `403 Forbidden`.

## External Stack Layouts

When deploying the Compose stack outside the checkout, copy the SearXNG
settings directory beside the Compose file:

```text
<stack-dir>/docker-compose.yaml
<stack-dir>/searxng/settings.yml
```

Set `SEARXNG_SECRET` in the active stack env file. If a bind mount is added or
changed after container creation, recreate the SearXNG service; a restart does
not add new mounts.

```bash
docker compose \
  --env-file <ORAC_HOME>/resources/config/orac.env \
  -f <ORAC_HOME>/resources/docker/oracle/docker-compose.yaml \
  --profile search \
  up -d --force-recreate orac-searxng
```

If port `8888` is unavailable, change `SEARXNG_PORT` in the active Compose env
file and update `base_url`, `host`, and `port` in `orac.ini`.

## Safety Boundaries

Orac validates search and fetch targets before use. The current retrieval path:

- rejects local, private, and internal address ranges
- validates redirect targets
- limits redirect count and response size
- accepts only supported textual content
- treats fetched text as evidence rather than prompt authority
- can require citations in generated responses

When the provider is unavailable or evidence cannot be fetched safely, Orac
fails closed instead of fabricating retrieved evidence.

Local ingested knowledge is a separate evidence source with separate
provenance. It reuses the normal dialogue pipeline rather than replacing this
SearXNG stack. Combined local and internet evidence is not part of the first
release. See [Dialogue Routing](dialogue-routing.md).

Person-fact corroboration and recent-death handling are configured under
`[retrieval.person_facts]`. See [Configuration Parameters](configuration.md).
