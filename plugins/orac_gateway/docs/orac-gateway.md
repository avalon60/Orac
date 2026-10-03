# Orac Gateway

## Architecture

The plugin owns only the HTTP listener, authentication binding, protocol
translation, and streaming response framing. Its managed service receives a
narrow host-injected `OracRequestProcessor`, model catalogue provider, and
embedding provider. Chat requests therefore follow the same Core retrieval,
web search, memory, governance, evidence, routing, and persistence path as
other Orac transports.

## Configuration

Copy or edit `plugin.ini` within the installed plugin snapshot. The bundled
default is safe for local development:

```ini
[gateway]
listen_host = 127.0.0.1
listen_port = 11435
authentication_mode = trusted_loopback
principal = orac_gateway
allowed_models =
max_request_bytes = 1048576
```

`trusted_loopback` cannot bind to a non-loopback address. For any remote
listener, select `bearer` and store `api_key` in the plugin secret vault. The
configured principal must already exist in Orac; the request body cannot
select a principal or enlarge its grants.

`allowed_models` is an optional comma-separated restriction applied on top of
Core's enabled model catalogue. An empty value does not create a second model
registry; it exposes the Core-authorised catalogue.

The plugin has no private database schema or APEX application. It reuses the
host model, principal, retrieval, evidence, conversation, and plugin-service
contracts.

## Installation and operation

Install the development source or the bundled plugin through the host-owned
installer:

```bash
bin/orac-plugin.sh install --source plugins/orac_gateway
# or
bin/orac-plugin.sh install --bundled orac_gateway
```

For bearer mode, store the credential before starting the service:

```bash
bin/plugin-pat-mgr.sh --plugin orac_gateway --set api_key
bin/plugin-pat-mgr.sh --plugin orac_gateway --check api_key
```

The configured `principal` must already exist and hold the required model and
corpus grants. Installing or enabling the plugin does not create that user or
grant access. Inspect the managed service with:

```bash
bin/orac-plugin.sh service status orac_gateway default --require-running
```

The `auto` start policy normally lets Orac supervise the service. A maintainer
can run a bounded foreground instance for diagnosis with
`bin/orac-plugin.sh service run orac_gateway default --duration-seconds 30`.

## Client endpoints

OpenAI-compatible clients use `http://host:port/v1`. Ollama-native clients,
including the inspected LocalMind version, use `http://host:port` because they
append `/api/chat`, `/api/tags`, and `/api/embed` themselves.

OpenAI streaming uses server-sent events and terminates with `[DONE]`.
Ollama-native streaming uses newline-delimited JSON and a final `done: true`
object. Closing a client stream closes the canonical Core stream and cancels
unfinished upstream processing.

An optional `X-Orac-Session-ID` header supplies a session label. The gateway
namespaces it beneath the authenticated principal before Core processes it.

Example OpenAI-compatible request in trusted-loopback mode:

```bash
curl -N http://127.0.0.1:11435/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-Q4-96K","stream":true,"messages":[{"role":"user","content":"What does John Elder say about memory in AI-OS?"}]}'
```

In bearer mode add `Authorization: Bearer <credential>`. Do not put a real
credential in source files, command history, documentation, or diagnostics.

## MVP limitations

This version is text-only. Client-managed tool definitions, assistant tool
calls, tool-result messages, images, structured output, and `/v1/responses`
are rejected explicitly rather than ignored. Orac's internal governed
retrieval remains available because it is owned by Core and is not exposed in
the external client's tool namespace.

Supported generation controls are `temperature`, `top_p`, `max_tokens`, and
`seed`; the Ollama equivalents include `num_predict`. Ollama `num_ctx` is
accepted as a client hint, while Core remains authoritative for actual context
budgeting. Ollama `keep_alive` is retained as request metadata, while Core's
provider lifecycle configuration remains authoritative.

Embedding requests are delegated only to Core's configured knowledge
embedding profile. Arbitrary models and arbitrary upstream URLs are not
accepted.

## Maintainer validation and troubleshooting

The main contract tests are `tests/test_orac_gateway.py`,
`tests/test_openai_adapter.py`, `tests/test_communications_security.py`, and
`tests/test_plugin_service_manager.py`. Run them with `PYTHONPATH=src` through
the project virtual environment.

If the listener does not start, check plugin service status, confirm that the
configured principal exists, confirm the bearer secret when applicable, and
verify that the listen port is free. `trusted_loopback` deliberately refuses a
non-loopback bind. The health endpoint reports only redacted service state;
request bodies, retrieved evidence, tool arguments, and credentials are not
written to access logs by the gateway.
