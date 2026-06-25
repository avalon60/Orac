# Orac Documentation

This directory contains the canonical user, operator, and maintainer
documentation for Orac. Start with the topic matching the task you are trying
to complete.

## Get Orac Running

- [Installation](installation.md): host prerequisites, database deployment,
  credentials, and first startup.
- [SQLcl Liquibase Database Deployment](database-liquibase-deployment.md):
  on-demand core and plugin database delta deployment boundaries.
- [Configuration Reference](configuration.md): every setting shipped in
  `resources/config/orac.ini`.
- [Docker Compose Deployment](docker-compose-deployment.md): stack locations,
  services, profiles, Dockge mirroring, and control commands.
- [APEX Administration](apex-administration.md): access and troubleshoot the
  administration application.
- [Backup and Restore](backup-restore.md): protect and recover local Orac state.

## Use and Extend Orac

- [Plugins](plugins.md): plugin manifests, lifecycle, policy, configuration,
  secrets, services, database payloads, and audit boundaries.
- [Home Assistant](../plugins/home_assistant/docs/home-assistant.md): configure
  credentials, synchronise inventory, control approved devices and scenes, and
  list devices by area.
- [Internet Retrieval](retrieval.md): configure SearXNG and Orac retrieval
  policy.
- [Runtime User Preferences](user_preferences.md): runtime preference
  precedence, validation, and TTS portability.
- [Voice Pipeline](voice-pipeline.md): wake word, recording, STT, TTS,
  playback, barge-in, and AEC.
- [Optional Atom Display](orac-atom-display.md): desktop display listener and
  event transport.

## Architecture and Protocols

- [Architecture Overview](../detailed-architecture.md)
- [Voice Turn Lifecycle](voice-turn-lifecycle.md)
- [Home Assistant Data Lifecycle](../plugins/home_assistant/docs/home-assistant-data-lifecycle.md)
- [Plugin Execution Boundaries](agent-guardrails/55-plugin-execution-boundaries.md)
- [Plugin Audit Persistence](plugin-audit-persistence.md)
- [Plugin Audit Database/API Design](plugin-audit-db-api-design.md)
- [Protocol Contract and Release Guide](../protocol/README.md)
- [Acoustic Echo Cancellation Design](aec-design.md)

## Development Controls

Agent and maintainer guardrails remain under
[`docs/agent-guardrails/`](agent-guardrails/) because their paths are checked by
repository tooling and referenced by `AGENTS.md`.

- [Project Principles](agent-guardrails/00-project-principles.md)
- [Architecture Boundaries](agent-guardrails/10-architecture-boundaries.md)
- [Python Standards](agent-guardrails/30-python-standards.md)
- [Frontend Vite React Standards](agent-guardrails/35-frontend-vite-react-standards.md)
- [Plugin Standards](agent-guardrails/50-plugin-standards.md)
- [Plugin Execution Boundaries](agent-guardrails/55-plugin-execution-boundaries.md)
- [Security and Risk](agent-guardrails/60-security-and-risk.md)
- [Context Management](agent-guardrails/70-context-management.md)

Planning documents and work-in-progress investigations remain separate from
canonical operating guidance and should not be treated as runtime contracts.
