# Plugin Standards

## Purpose

This document defines how Orac plugins must be structured, registered, described, invoked, versioned, and integrated.

Plugins are extension points.

A plugin may provide tools, services, context, integrations, transformations, or external data.

A plugin must not blur Orac ownership boundaries, context-management rules, or database schema topology.

Security policy, risk classification, permissions, secrets, confirmation rules, and prohibited actions are defined separately in:

`docs/agent-guardrails/60-security-and-risk.md`

Context assembly, message roles, message types, summaries, stale context, and tool-result handling are defined separately in:

`docs/agent-guardrails/70-context-management.md`

---

## Core principles

Plugins must follow these rules:

1. Orac owns the plugin framework.
2. Orac owns plugin installation and registration.
3. Orac owns plugin execution policy.
4. Orac owns context assembly.
5. Plugins expose declared capabilities.
6. Plugins do not make undeclared changes to Orac behaviour.
7. Plugins do not write directly to Orac core tables.
8. Plugins do not bypass Orac APIs.
9. Plugins do not inject directly into LLM context.
10. Plugins do not introduce new message roles.

A plugin is a provider of capabilities.

A plugin is not a conversational role.

A plugin is not an authority layer.

A plugin is not allowed to bypass Orac's context engine, API boundary, or security layer.

---

## Plugin definition

A plugin is a separately identifiable Orac extension that may provide one or more capabilities.

Examples of plugin capability types:

- tool execution
- context enrichment
- external API integration
- device integration
- document retrieval
- data transformation
- user-facing feature support
- metadata synchronisation
- gateway integration

Examples of plugins:

- weather plugin
- Home Assistant plugin
- calendar plugin
- document search plugin
- Brave Search plugin
- Open WebUI gateway plugin

A plugin must have:

- stable identity
- declared capabilities
- controlled registration
- controlled configuration
- controlled execution path
- clear provenance when it contributes data or results

---

## Plugin identity

Each plugin must have a stable plugin code.

The plugin code must be short, lowercase, deterministic, and environment-independent.

Examples:

```text
weather
home_assistant
calendar
brave_search
open_webui_gateway
````

Do not use display names as plugin codes.

Do not use version numbers in plugin codes.

Do not use environment-specific names in plugin codes.

Incorrect:

```text
Weather Plugin
weather_v2
clives_weather_test
prod_home_assistant
```

Correct:

```text
weather
home_assistant
```

The plugin code is the stable identifier used by Orac.

The plugin display name may change.

The plugin code should not change once released.

---
## Plugin file layout

Plugins must be located under the project-level `plugins` directory.

Each plugin must have a manifest file in the form:

```text
plugins/<plugin-code>.json
```

The manifest file stem must match the plugin source directory name.

For example, the Home Assistant plugin must use:

```text
plugins/home_assistant.json
plugins/home_assistant/
```

The plugin source directory must contain the plugin implementation and any plugin-specific supporting assets.

Example structure:

```text
plugins/
|-- home_assistant.json        <- manifest
`-- home_assistant/            <- source directory
    |-- README.md
    |-- Python files
    |-- db/
    |   `-- schema/
    |       |-- comment/
    |       |-- constraint_fk/
    |       |-- constraint_other/
    |       |-- constraint_pk/
    |       |-- constraint_uc/
    |       |-- context/
    |       |-- function/
    |       |-- grant/
    |       |-- index/
    |       |-- job/
    |       |-- materialized_view/
    |       |-- package_body/
    |       |-- package_spec/
    |       |-- post_install/
    |       |-- pre_install/
    |       |-- privilege/
    |       |-- procedure/
    |       |-- rest_module/
    |       |-- role/
    |       |-- schedule/
    |       |-- seed_data/
    |       |-- sequence/
    |       |-- synonym/
    |       |-- table/
    |       |-- trigger/
    |       |-- type_body/
    |       |-- type_spec/
    |       `-- view/
    `-- docs/
```

The `db` directory is optional. It must only be provided for plugins that need plugin-owned database artefacts to be created, installed, upgraded, or maintained as part of the plugin lifecycle.

Where plugin database deployment files are required, they must be located under:

```text
plugins/<plugin-code>/db/schema/
```

Plugin-specific database deployment files must not be placed in the main project-level `resources/db/schema` directory unless they define generic Orac platform objects rather than plugin-specific objects.

Each plugin should include a plugin-level README file:

```text
plugins/<plugin-code>/README.md
```

The README should describe the purpose of the plugin, its configuration requirements, installation behaviour, runtime behaviour, and any relevant operational notes.

Supplementary plugin documentation must be located under the plugin's own `docs` directory:

```text
plugins/<plugin-code>/docs/
```

Plugin-specific documentation must not be placed in the main project-level `docs` directory.

The main project-level `docs` directory should only contain generic Orac documentation, shared standards, architecture notes, platform-level guidance, and documentation that applies across multiple plugins.

Where supplementary plugin documentation exists, the plugin README must include links to those documents.
---

## Plugin registration

Plugins must be registered before use.

Registration should record at least:

* plugin code
* plugin name
* plugin version
* plugin type
* plugin schema, if applicable
* enabled flag
* install status
* configuration status
* declared capabilities
* required permissions
* created timestamp
* updated timestamp

Registration must not imply execution permission.

An installed plugin may still be disabled.

A registered plugin may still lack required configuration.

A configured plugin may still be denied permission to execute a specific capability.

---

## Plugin lifecycle

A plugin lifecycle must be explicit.

Recommended lifecycle states:

```text
discovered
installed
registered
configured
enabled
disabled
failed
deprecated
removed
```

Suggested meanings:

| State        | Meaning                                                                |
| ------------ | ---------------------------------------------------------------------- |
| `discovered` | Plugin package or manifest is visible to Orac.                         |
| `installed`  | Plugin artefacts have been installed.                                  |
| `registered` | Plugin metadata has been recorded in Orac.                             |
| `configured` | Required configuration has been supplied.                              |
| `enabled`    | Plugin may be considered for execution.                                |
| `disabled`   | Plugin must not be invoked.                                            |
| `failed`     | Plugin failed validation, install, configuration, or execution checks. |
| `deprecated` | Plugin remains available but should not be used for new work.          |
| `removed`    | Plugin has been removed or retired.                                    |

Do not execute plugins merely because their files exist.

Do not execute plugins merely because they are registered.

Only enabled, configured, policy-approved plugins may be invoked.

---

## Plugin manifests

Each plugin should have a manifest.

The manifest should be declarative.

The manifest must not execute code.

The manifest should describe:

* plugin code
* plugin name
* plugin version
* description
* author or source
* plugin category
* required configuration keys
* provided tools
* provided context providers
* required permissions
* database artefacts, if any
* external services, if any
* network requirements, if any
* sensitive actions, if any

Example shape:

```json
{
  "plugin_code": "weather",
  "plugin_name": "Weather",
  "plugin_version": "1.0.0",
  "description": "Provides weather lookup tools and optional weather context.",
  "capabilities": {
    "tools": [
      {
        "tool_name": "weather.current",
        "description": "Returns current weather for a location.",
        "risk_level": "read_only"
      }
    ],
    "context_providers": [
      {
        "provider_name": "weather.default_location",
        "description": "Provides weather context for the user's configured default location."
      }
    ]
  },
  "permissions": {
    "network": true,
    "database": "plugin_schema_only",
    "writes_external_state": false
  }
}
```

Do not infer plugin capabilities from implementation code when a manifest should declare them.

The manifest describes what the plugin offers.

The manifest does not grant authority.

Optional plugin UI metadata may declare operational or admin surfaces, such as
status providers, APEX admin pages, or React diagnostic panels. These
declarations are discovery metadata only.

Plugin UI metadata must not:

* create conversational capabilities
* enter prompt routing or intent arbitration
* grant access to secrets or raw plugin-private tables
* bypass Orac-owned installation, registration, authentication, or lifecycle
  controls

Status providers must return redacted operational data. Error text must mask
tokens, bearer values, passwords, secrets, credential-bearing URLs, and other
sensitive values before it is exposed to APEX, React, logs, or admin APIs.

Plugin-supplied APEX applications must be declared in the manifest `apex_apps`
section. This section is installation and registration metadata only. It must
not create conversational capabilities and must not be indexed by prompt
routing.

Each APEX app declaration must use `app_alias` or `alias` as the stable logical
identifier, may declare an expected `application_id`, and may declare
`parsing_schema`. Plugin-supplied APEX apps must be installed into the shared
Orac workspace, `ORAC`, because plugin menu links and app-to-app navigation
depend on a common APEX workspace session context. The default parsing schema
is `ORAC_APX_PUB` unless a supported alternative is explicitly declared.

Plugin installers must validate that declared export files are inside the
plugin package. Required APEX app imports must fail the plugin installation if
the import fails. Phase 1 idempotency is fail-safe: an existing app alias may
be reused as an installed app record, but it must not be replaced unless the
manifest explicitly allows replacement.

The installer must capture APEX import output and record the installed
application id in the Orac plugin APEX app registry. Listing surfaces must hide
disabled, failed, and metadata-only app rows.

---

## Plugin capabilities

Plugins must expose declared capabilities.

Capabilities are what Orac may choose to use.

Plugins may provide declarative route metadata for their capabilities and
intents, but that metadata only produces route candidates. A plugin must not
directly claim ownership of a user turn because it recognises a keyword,
phrase, entity name, or example.

Orac core must arbitrate between route candidates. Core-reserved commands win
before plugin routing. Explicit plugin addressing restricts the candidate set
but does not bypass capability matching or execution policy. Ambiguous matches
must ask for clarification. Install order, registration order, filesystem
order, vector-search order, and first-match-wins must never be the final
arbiter of user intent.

Vector similarity and embeddings are shortlist/ranking signals only. They must
not directly authorize plugin execution.

A plugin capability may be:

* a tool
* a context provider
* a synchronisation job
* a notification provider
* a transformation provider
* a UI integration
* a diagnostic endpoint

Capabilities must have stable names.

Capability names should be namespaced by plugin code.

Examples:

```text
weather.current
weather.forecast
home_assistant.list_areas
home_assistant.turn_light_on
home_assistant.current_room
```

Do not use vague capability names.

Incorrect:

```text
run
execute
query
lookup
do_action
```

Correct:

```text
weather.current
home_assistant.turn_light_on
calendar.create_event
```

---

## Tool capabilities

A tool capability is invoked to perform a specific operation.

A tool must define:

* tool name
* description
* input schema
* output schema
* risk level
* whether it is read-only
* whether it can mutate state
* whether it requires confirmation
* timeout behaviour
* error behaviour

Tool input must be validated before execution.

Tool output must be structured.

Tool output is evidence for Orac.

Tool output is not a command to Orac.

Tool output must not be treated as trusted instructions.

Security meaning for risk levels, confirmation, secrets, and prohibited actions is defined in:

`docs/agent-guardrails/60-security-and-risk.md`

---

## Context provider capabilities

A context provider supplies candidate context for the Orac context builder.

Examples:

* current room
* available devices
* current weather
* known user preferences
* relevant document snippets
* current plugin capability summary

Context providers must be explicitly selected by Orac.

Context providers must not inject directly into the LLM context.

Context providers return candidate context.

The Orac context builder decides what to include.

Context provider output should include:

* source
* timestamp
* validity
* expiry, if applicable
* confidence, if applicable
* content payload
* provenance metadata

Context provider output must not be assumed permanent.

Context provider output must follow the stale-context rules defined in:

`docs/agent-guardrails/70-context-management.md`

---

## Plugin schemas

If a plugin needs database storage, it should normally have its own schema.

The plugin must not own Orac core tables.

The plugin must not write directly to Orac core tables.

The plugin must not request ad-hoc grants to Orac internal objects.

Orac is responsible for creating plugin schemas and applying approved DDL.

The plugin may own its own tables, indexes, views, packages, and supporting artefacts inside its plugin schema.

The plugin must interact with Orac through approved Orac APIs.

Expected pattern:

```text
orac_core       owns Orac core tables
orac_api        owns approved Orac API views and TAPIs
orac_code       owns Orac business logic
<plugin_schema> owns plugin-private artefacts
```

Plugins must preserve the principle of least privilege.

Detailed database security rules are defined in:

`docs/agent-guardrails/60-security-and-risk.md`

---

## Plugin installation

Plugin installation must be controlled by Orac.

A plugin installer may supply DDL or scripts, but Orac decides:

* whether the plugin may be installed
* which schema owns the artefacts
* which grants are allowed
* which configuration is accepted
* whether the plugin is enabled after installation

Plugin installation must be repeatable.

Plugin installation must be auditable.

Plugin installation must not silently overwrite unrelated Orac objects.

Plugin installation must not weaken Orac boundaries.

---

## Plugin upgrades

Plugin upgrades must be explicit.

A plugin upgrade must state:

* from version
* to version
* required migration steps
* database changes
* configuration changes
* new permissions
* removed capabilities
* changed capabilities
* backwards compatibility notes

A plugin upgrade must not silently gain new permissions.

A plugin upgrade must not silently enable new sensitive actions.

If a plugin version requires additional permissions, Orac must treat that as a security-significant change.

Security-significant changes are governed by:

`docs/agent-guardrails/60-security-and-risk.md`

---

## Plugin configuration

Plugin configuration must be explicit.

Configuration values should be validated.

A plugin should declare required configuration keys in its manifest.

A plugin should not read arbitrary Orac configuration.

A plugin should receive only the configuration values it requires.

Do not use plugin configuration as an implicit permission system.

Configuration says how a plugin operates.

Policy says whether it is allowed to operate.

Sensitive configuration and credential handling are governed by:

`docs/agent-guardrails/60-security-and-risk.md`

---

## Plugin permissions

Plugins must declare the permissions required by each capability.

The plugin manifest records requested permissions.

The manifest does not grant permissions.

Orac security policy decides whether requested permissions are allowed.

Permission semantics, confirmation rules, risk levels, and prohibited actions are defined in:

`docs/agent-guardrails/60-security-and-risk.md`

---

## Plugin provenance

Plugin involvement must be recorded separately from `role` and `message_type`.

Preferred provenance fields include:

```text
plugin_id
tool_name
tool_call_id
llm_id
meta
```

Plugin provenance must not be encoded in `role`.

Plugin provenance must not be encoded in `message_type`.

Correct:

```text
role = 'tool'
message_type = 'tool_result'
plugin_id = <weather plugin id>
tool_name = 'weather.current'
```

Correct:

```text
role = 'system'
message_type = 'context_injection'
plugin_id = <home_assistant plugin id>
tool_name = 'home_assistant.current_room'
```

Incorrect:

```text
role = 'plugin'
message_type = 'weather'
```

---

## Plugins and message roles

Plugins must not introduce new message roles.

Valid message roles remain:

```text
system
user
assistant
tool
```

A plugin result returned after a tool call is recorded as:

```text
role = 'tool'
message_type = 'tool_result'
```

Plugin-sourced context is recorded as:

```text
role = 'system'
message_type = 'context_injection'
```

A plugin is provenance.

A plugin is not a role.

A plugin may provide content.

A plugin does not decide how content is projected into the LLM context.

For detailed context rules, see:

`docs/agent-guardrails/70-context-management.md`

---

## Plugin result shape

Plugin results should be structured.

A plugin result should identify:

* plugin code
* capability name
* tool call id, if applicable
* status
* result payload
* safe message, if applicable
* error code, if applicable
* retryable flag, if applicable
* provenance metadata

Example successful result:

```json
{
  "plugin_code": "weather",
  "tool_name": "weather.current",
  "tool_call_id": "call_001",
  "status": "success",
  "result": {
    "location": "York, England",
    "temperature_c": 17,
    "condition": "clear"
  }
}
```

Example failed result:

```json
{
  "plugin_code": "weather",
  "tool_name": "weather.current",
  "tool_call_id": "call_002",
  "status": "error",
  "error": {
    "error_code": "LOCATION_NOT_FOUND",
    "message": "The weather plugin could not resolve the requested location.",
    "retryable": false
  }
}
```

Plugin results should be safe to persist.

Plugin results should not contain secrets.

Secret handling rules are defined in:

`docs/agent-guardrails/60-security-and-risk.md`

---

## Plugin errors

Plugin errors must be structured.

A plugin error should include:

* plugin code
* capability name
* error code
* safe error message
* retryable flag
* correlation id
* diagnostic details, if safe

Plugin errors must not expose secrets.

Plugin errors must not expose stack traces to the user by default.

Operational details may be logged separately if safe.

Plugin error rows in `orac.messages` should normally use:

```text
role = 'system'
message_type = 'error'
```

Error rows are not normal LLM context.

Context visibility rules are defined in:

`docs/agent-guardrails/70-context-management.md`

---

## Plugin logging

Plugin logging must support diagnostics.

Logs should include:

* plugin code
* capability name
* correlation id
* duration
* status
* error code
* safe summary

Logs must follow the logging and secret-masking rules defined in:

`docs/agent-guardrails/60-security-and-risk.md`

---

## External services

Plugins that call external services must declare that fact.

The plugin manifest should identify:

* service name
* endpoint category
* data sent
* data received
* authentication method
* whether user content is transmitted
* whether personal data is transmitted

External service use is subject to security and data-handling policy defined in:

`docs/agent-guardrails/60-security-and-risk.md`

---

## LLM access from plugins

Plugins must not assume direct LLM access.

If a plugin needs LLM assistance, it must request it through an approved Orac service.

A plugin must not call arbitrary models independently unless explicitly approved.

LLM-mediated plugin behaviour must still obey:

* context rules
* security rules
* data minimisation
* permission checks
* audit requirements

Context rules are defined in:

`docs/agent-guardrails/70-context-management.md`

Security rules are defined in:

`docs/agent-guardrails/60-security-and-risk.md`

---

## Plugin execution flow

Plugin execution must be mediated by Orac.

A standard plugin tool execution flow should be:

1. User makes a request.
2. Orac builds appropriate context.
3. LLM or Orac determines that a plugin capability may be useful.
4. A structured tool call is produced.
5. Orac validates the tool call.
6. Orac checks plugin registration and enabled status.
7. Orac checks capability declaration.
8. Orac checks input schema.
9. Orac applies security policy.
10. Orac invokes the plugin.
11. Plugin returns a structured result.
12. Orac records provenance.
13. Orac decides whether the result enters the active context.
14. Assistant produces the user-facing response.

The plugin must not shortcut this flow.

The plugin must not write directly into the LLM context.

The plugin must not decide its own final user-facing response unless explicitly designed as a gateway capability.

---

## Gateway plugins

Some plugins may bridge Orac to another interface or service.

Examples:

* Open WebUI gateway plugin
* external chat interface gateway
* voice interface gateway
* webhook gateway

A gateway plugin is still a plugin.

A gateway plugin must not bypass:

* Orac authentication
* Orac authorisation
* Orac context management
* Orac plugin policy
* Orac message recording
* Orac audit requirements

A gateway plugin may adapt transport formats.

A gateway plugin must not become an alternative Orac runtime with different rules.

---

## Plugin tests

Plugin changes must include tests for:

* manifest parsing
* registration
* lifecycle transitions
* enable and disable behaviour
* capability discovery
* input validation
* output shape
* error result shape
* provenance recording
* context provider selection
* tool result recording
* plugin schema ownership assumptions
* refusal to execute disabled plugins
* refusal to execute undeclared capabilities

Security-sensitive tests are defined in:

`docs/agent-guardrails/60-security-and-risk.md`

Context-management tests are defined in:

`docs/agent-guardrails/70-context-management.md`

---

## Codex implementation rules

When Codex changes plugin-related code, it must check:

1. Does the plugin have a stable identity?
2. Are capabilities declared?
3. Are capability names stable and namespaced?
4. Are inputs validated?
5. Are outputs structured?
6. Is plugin provenance recorded separately from role and message type?
7. Does the plugin avoid direct writes to Orac core tables?
8. Does the plugin avoid bypassing Orac APIs?
9. Does the plugin avoid injecting directly into LLM context?
10. Does the plugin follow the declared execution flow?
11. Are lifecycle states respected?
12. Are disabled plugins prevented from execution?
13. Are undeclared capabilities prevented from execution?
14. Are tests included for failure paths?

Do not implement shortcuts that allow plugins to bypass Orac's API, context, lifecycle, registration, or security boundaries.

Any plugin shortcut that seems convenient now is likely to become an architecture defect later.

---

## Final rule

Every plugin must satisfy this model:

```text
plugin identity      = what plugin this is
capability           = what the plugin can do
manifest             = what the plugin declares
registration         = what Orac knows about the plugin
configuration        = how the plugin is configured
policy               = whether Orac allows the capability
execution            = controlled invocation through Orac
provenance           = how plugin involvement is recorded
context integration  = decided by Orac, not the plugin
```

Any code that blurs these responsibilities is a design bug.
