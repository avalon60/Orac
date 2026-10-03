# Orac Gateway

Orac Gateway is a managed service plugin that exposes Orac's governed inference
pipeline to OpenAI-compatible and Ollama-native clients. Requests enter Core
through `OracRequestProcessor`; the plugin does not own retrieval, model
routing, evidence, permissions, or conversation persistence.

The MVP endpoints are:

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`
- `GET /api/tags`
- `POST /api/chat`
- `POST /api/embed`

See [`docs/orac-gateway.md`](docs/orac-gateway.md) for configuration,
authentication, compatibility, and current limitations.
