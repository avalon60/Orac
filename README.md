![Orac Logo](./assets/images/OracLogoMinimal.png)

<h1 align="center">Orac - Version 0.1.0</h1>

<p align="center">
  <em>Your retro-futuristic, locally operated AI assistant.</em>
</p>

<p align="center">
  <a href="https://github.com/Avalon60/orac"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
</p>

## What Orac Is

Orac is a Linux-hosted conversational AI system built around a local LLM,
Oracle Database, a voice pipeline, optional internet retrieval, and a governed
plugin runtime. It is designed for local operation and explicit control over
credentials, retrieval, plugins, and home-automation integrations.

## Current Capabilities

- Local LLM conversations through Ollama or another compatible configured
  service.
- Persistent conversation and configuration data in Oracle Database.
- Local speech recognition with Faster Whisper.
- Wake-word activation with openWakeWord, plus optional Porcupine support.
- Speech synthesis through Kokoro with Piper fallback.
- Explicit or policy-controlled internet retrieval through a local SearXNG
  service.
- Deterministic, core-owned dialogue routing across plugins, authorised local
  knowledge, internet retrieval, and ordinary LLM conversation.
- Manifest-driven plugins with scoped configuration, secrets, execution policy,
  service lifecycle, database deployment, packaged APEX application
  installation, shared navigation, and audit boundaries.
- Home Assistant inventory synchronisation, area/device listings, temperature
  and humidity queries, live light-state read-back, and allowlisted interaction
  with lights, switches, and scenes.
- Rich light interaction for supported Home Assistant entities, including
  brightness, colour, and colour-temperature changes validated against live
  device capabilities.
- The bundled Weather plugin answers current-condition and short-forecast
  questions for explicit or configured locations through Open-Meteo.
- The bundled Drop Box plugin scans configured folders, creates durable jobs,
  and hands verified local text and Markdown documents to Core-managed
  ingestion, chunking, embedding, and provenance services. Ingested content can
  support opt-in, scope-authorised grounded dialogue retrieval.
- Browser and desktop display surfaces for runtime state and transcripts.
- Oracle APEX administration, including framework-managed plugin applications
  such as Home Assistant Status and Drop Box Admin, plus backup and restore
  tooling for the local deployment.

## Development Status

Orac is under active development. Several foundations are operational, while
some advertised capabilities remain intentionally constrained:

- Home Assistant mutations are deliberately limited to exact, allowlisted
  light, switch, and scene operations. Arbitrary services, whole-home commands,
  and control of locks, alarms, climate, covers, fans, scripts, and automations
  are not enabled.
- Local-knowledge dialogue retrieval is disabled by default and currently
  supports UTF-8 text and Markdown ingestion. The shipped hash embedding is
  development/test infrastructure, lexical relevance is the current evidence
  gate, and native Oracle vector search is not yet part of the runtime.
- Barge-in, native playback, and acoustic echo cancellation include
  experimental modes and require explicit configuration.
- Media control remains a policy-blocked scaffold, and the OpenAI-compatible
  gateway settings are reserved for a future service.
- Future work is kept separate from the current-capability documentation.

## Main Components

| Component | Role | Required |
|---|---|---|
| Orac AI engine | Conversation orchestration, plugins, context, retrieval | Yes |
| Oracle Database + ORDS/APEX | Persistence, core administration, and framework-managed plugin APEX applications | Yes for the supported local stack |
| Local LLM service | Model inference, normally Ollama | Yes |
| SearXNG | Local/private search provider | When internet retrieval is enabled |
| Faster Whisper | Local speech-to-text | For voice operation |
| Kokoro or Piper | Local text-to-speech | For spoken responses |
| Home Assistant plugin | Inventory, live state and sensor queries, and allowlisted light/switch/scene interaction | Optional |
| Drop Box plugin + Core knowledge | Scheduled local document discovery, durable ingestion, and scope-authorised grounded retrieval | Optional |
| Weather plugin | Open-Meteo current conditions and short forecasts | Optional |

Orac uses SearXNG as its local/private search provider. See
[Internet Retrieval](docs/retrieval.md) for installation, configuration, and
troubleshooting.

## Quick Start

The supported deployment path assumes Linux, Docker Engine with Buildx, `bash`,
`sudo`, Python 3.12+, and a local checkout.

```bash
git clone https://github.com/Avalon60/orac.git
cd orac
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then:

1. Review `resources/config/orac.env` and `resources/config/orac.ini`.
2. Create the installer database credential with `bin/dbconn-mgr.sh -c orac`.
3. Deploy the local database with `bin/orac-db-deploy.sh`.
4. Start the complete stack with `bin/orac-ctl.sh start`.
5. Confirm status with `bin/orac-ctl.sh status`.

Read [Installation](docs/installation.md) before deploying a new host. The
deployment script currently supports only `TOPOLOGY=db-local`.

## Documentation

- [Documentation index](docs/README.md)
- [Installation](docs/installation.md)
- [Configuration reference](docs/configuration.md)
- [Runtime user preferences](docs/user_preferences.md)
- [Plugins](docs/plugins.md)
- [Home Assistant](plugins/home_assistant/docs/home-assistant.md)
- [Drop Box and local document ingestion](plugins/drop_box/README.md)
- [Weather](plugins/weather/README.md)
- [Internet retrieval](docs/retrieval.md)
- [Dialogue routing and local knowledge](docs/dialogue-routing.md)
- [Voice pipeline](docs/voice-pipeline.md)
- [APEX administration](docs/apex-administration.md)
- [Backup and restore](docs/backup-restore.md)
- [Docker Compose deployment](docs/docker-compose-deployment.md)
- [Architecture overview](detailed-architecture.md)

## Common Commands

```bash
bin/orac-ctl.sh start
bin/orac-ctl.sh stop
bin/orac-ctl.sh restart
bin/orac-ctl.sh status
bin/orac-ctl.sh compose-check
bin/orac-ctl.sh logs
```

Use `bin/orac.sh` only when controlling the host AI engine independently from
the Compose-managed services.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## About the Name

Orac is named after the computer from *Blake's 7*, combining a retro science
fiction reference with a modern local AI system.
