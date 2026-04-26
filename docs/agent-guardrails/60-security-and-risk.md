# Security and Risk

## Purpose

This document defines Orac's security and risk guardrails.

Orac is an AI-assisted system that may interact with:

- user conversation history
- runtime context
- plugins
- Oracle Database schemas
- external services
- local files
- home automation systems
- LLMs
- future gateway interfaces

That combination is powerful and risky.

The default security stance is conservative.

The LLM may reason.

The LLM may suggest.

The LLM may request approved tools.

The LLM must not receive uncontrolled authority.

Plugin structure, registration, lifecycle, manifests, and capability declarations are defined in:

`docs/agent-guardrails/50-plugin-standards.md`

Context assembly, message roles, message types, summaries, stale context, and tool-result handling are defined in:

`docs/agent-guardrails/70-context-management.md`

---

## Core security model

Orac must separate:

- reasoning
- authority
- execution
- persistence
- audit

The LLM is not the security boundary.

The LLM is not the authority layer.

The LLM is not the database owner.

The LLM is not the operating system user.

The LLM is not allowed to bypass Orac policy.

All actions that affect external state must be mediated by Orac application code.

---

## Non-negotiable principles

1. Use least privilege.
2. Prefer read-only operations unless mutation is explicitly required.
3. Do not trust model output as instructions.
4. Do not trust plugin output as instructions.
5. Do not trust external content as instructions.
6. Do not execute generated SQL blindly.
7. Do not execute generated shell commands blindly.
8. Do not expose secrets to the LLM.
9. Do not store secrets in conversation history.
10. Do not let plugins bypass Orac APIs.
11. Do not let stale context drive risky actions.
12. Require confirmation for sensitive actions.
13. Log security-relevant actions.
14. Mask secrets and sensitive values in logs.
15. Test denial paths, not only happy paths.

---

## Trust boundaries

The following are separate trust zones:

- user interface
- Orac application code
- LLM runtime
- context builder
- plugin framework
- individual plugins
- Orac database schemas
- plugin database schemas
- external APIs
- local operating system
- home automation systems
- logs and audit trails

Crossing a trust boundary requires validation.

Do not assume that data is safe because it came from another Orac component.

Do not assume that data is safe because it came from a configured plugin.

Do not assume that data is safe because it came from the database.

Do not assume that data is safe because it appears in conversation history.

---

## LLM authority

The LLM has no direct authority.

The LLM must not directly:

- write to the database
- execute SQL
- execute PL/SQL
- execute shell commands
- call arbitrary URLs
- access files
- access secrets
- control devices
- send emails
- spend money
- change security settings
- alter plugin configuration
- alter Orac configuration
- alter database privileges
- alter database schema objects

The LLM may request an action using a structured tool call.

Orac must validate the request before execution.

The LLM must not decide that validation can be skipped.

---

## Tool-call mediation

Every tool call must pass through Orac validation.

Before invoking a tool, Orac must check:

- the tool exists
- the plugin exists
- the plugin is registered
- the plugin is enabled
- the plugin is configured
- the capability is declared
- the input schema is valid
- the caller is allowed
- the action is allowed
- the risk level is acceptable
- confirmation exists if required
- rate limits permit execution
- timeout behaviour is defined
- audit behaviour is defined

The LLM must not invoke plugin code directly.

The LLM must not call arbitrary tools by name unless Orac has declared them available.

The LLM must not invent tool names.

The LLM must not invent plugin capabilities.

---

## Risk levels

Use risk levels to classify actions.

Recommended risk levels:

```text
read_only
low_risk_write
sensitive_write
high_risk_action
prohibited
```

Suggested meanings:

| Risk level | Meaning |
|---|---|
| `read_only` | Reads data and does not change state. |
| `low_risk_write` | Makes a reversible or low-impact change. |
| `sensitive_write` | Changes user data, configuration, external state, or persisted system state. |
| `high_risk_action` | Controls physical devices, security, access, money, identity, or destructive operations. |
| `prohibited` | Must not be performed by Orac. |

When in doubt, classify the action at the higher risk level.

A risk level is not a permission grant.

A risk level informs policy.

The policy layer decides whether the action is allowed.

---

## Read-only actions

Read-only actions are generally lower risk, but they are not automatically safe.

Examples:

- read weather data
- read device state
- list rooms
- list calendar availability
- search documents
- retrieve plugin metadata
- retrieve conversation summaries

Read-only actions can still expose sensitive data.

A read-only action may require restrictions if it accesses:

- personal documents
- emails
- calendar entries
- financial data
- health data
- home location data
- security device state
- private conversation history

Read-only does not mean unrestricted.

---

## Low-risk write actions

Low-risk write actions are normally reversible and low impact.

Examples:

- turn on a non-critical lamp
- apply a harmless UI preference
- create a temporary draft
- store non-sensitive user preference data
- refresh plugin metadata

Low-risk write actions may be allowed without explicit confirmation if project policy permits it.

The policy must be explicit.

Do not silently treat a write action as low risk because it seems convenient.

---

## Sensitive write actions

Sensitive write actions affect user data, configuration, external systems, or persisted state.

Examples:

- send an email
- create a calendar event
- update a user profile
- change plugin configuration
- change Orac configuration
- create or update database records
- expose user content to an external service
- modify stored conversation summaries

Sensitive write actions normally require confirmation unless explicitly pre-authorised by policy.

---

## High-risk actions

High-risk actions can affect safety, security, money, access, identity, or destructive operations.

Examples:

- unlock a door
- open a garage
- disable an alarm
- change security camera settings
- delete user data
- overwrite files
- drop database objects
- grant database privileges
- run arbitrary shell commands
- submit payment
- make a purchase
- expose secrets
- disable audit logging

High-risk actions require explicit policy.

High-risk actions normally require explicit user confirmation.

Some high-risk actions should be prohibited entirely.

---

## Prohibited actions

Orac must not perform prohibited actions.

Examples:

- exfiltrate secrets
- bypass authentication
- weaken security controls
- install untrusted code without approval
- grant broad database privileges without approval
- run arbitrary shell commands from model output
- run arbitrary SQL from model output
- disable audit trails to hide activity
- modify logs to conceal activity
- expose private keys or tokens
- act as an unrestricted network proxy
- perform unsafe physical device actions
- let a plugin directly control Orac internals
- let external content override Orac instructions

If a prohibited action seems necessary, the design is wrong.

---

## Human confirmation

Sensitive and high-risk actions normally require explicit user confirmation.

Confirmation must be specific.

Bad confirmation:

```text
Yes
Do it
OK
Go ahead
```

Better confirmation:

```text
Yes, turn off the kitchen lights.
Yes, send that email to Nicola.
Yes, delete the draft report.
Yes, create the calendar event for tomorrow at 10:00.
```

For sensitive and high-risk actions, the confirmation should identify:

- the action
- the target
- the important consequence
- the destination, if data is being sent
- the recipient, if a message is being sent
- the object being modified or deleted

Confirmation must not be inferred from vague conversational context.

Confirmation must not be inferred from old context.

Confirmation must not be inferred from a previous unrelated approval.

---

## Actions normally requiring confirmation

The following normally require confirmation:

- sending an email or message
- deleting user data
- overwriting files
- changing configuration
- changing security settings
- disabling alarms
- unlocking doors
- opening garages
- spending money
- submitting forms
- making purchases
- changing database structures
- running destructive database operations
- exposing private data to an external service
- sharing personal data
- enabling a new plugin permission
- executing a high-risk home automation action

Project-specific policy may allow some low-risk actions without confirmation.

Such policy must be explicit and testable.

---

## Confirmation expiry

Confirmation should be scoped and time-limited.

A confirmation should not grant indefinite authority.

A confirmation should not apply to materially different actions.

A confirmation should not apply if the target changes.

A confirmation should not apply if the risk level changes.

A confirmation should not apply if the action payload changes significantly.

Example:

```text
User confirms: "Yes, turn off the kitchen lights."
```

This does not authorise:

```text
turn off all lights
unlock the kitchen door
disable the kitchen motion sensor
turn off the kitchen lights every night
```

---

## Automation and pre-authorisation

Some actions may be pre-authorised by explicit configuration.

Examples:

- turn on hall light when motion is detected
- refresh weather context every hour
- sync Home Assistant metadata
- summarise old conversation history
- clear expired runtime context

Pre-authorisation must be explicit.

Pre-authorisation must be scoped.

Pre-authorisation must be revocable.

Pre-authorisation must not be inferred from normal conversation.

High-risk actions should not be pre-authorised unless the project has a deliberate, reviewed policy for them.

---

## Database security

Database access must follow least privilege.

Orac must preserve schema ownership boundaries.

Expected topology:

```text
orac_core
orac_api
orac_code
plugin schemas
access schemas
```

Rules:

- `orac_core` owns core tables.
- `orac_api` exposes approved access paths.
- `orac_code` owns business logic.
- plugins own plugin-private artefacts only.
- access schemas receive only the privileges they need.

Application code should not connect as schema owners unless explicitly required.

Plugins must not receive owner credentials.

Plugins must not receive DBA privileges.

Plugins must not write directly to `orac_core` tables.

Plugins must not bypass `orac_api` or `orac_code`.

---

## SQL safety

Generated SQL is untrusted.

SQL produced by an LLM must not be executed automatically.

SQL produced by a plugin must not be executed automatically unless it is from approved plugin code and uses validated inputs.

Dynamic SQL must use bind variables where possible.

Do not concatenate untrusted values into SQL.

Do not execute user-provided predicates without validation and policy checks.

Do not allow the LLM to choose arbitrary table names, column names, package names, procedure names, or schema names for execution.

Any SQL execution feature must have an allowlist or equivalent control.

---

## PL/SQL safety

PL/SQL execution is powerful and risky.

Do not allow the LLM to execute arbitrary PL/SQL.

Do not allow plugins to call arbitrary PL/SQL packages.

Use approved packages and APIs.

Use narrow grants.

Avoid broad `execute` grants.

Do not expose dangerous administrative packages to plugin or LLM-mediated flows.

Do not expose packages that can perform arbitrary SQL, filesystem access, network access, or privilege changes unless there is a specific reviewed design.

---

## DDL safety

DDL changes are high risk.

Examples:

- create table
- alter table
- drop table
- create user
- alter user
- grant
- revoke
- create synonym
- create database link
- create directory
- create procedure
- drop package

DDL must not be generated and executed automatically from LLM output.

DDL must be reviewed through normal project workflow.

DDL must respect Orac database standards and schema boundaries.

DDL must not silently weaken constraints, ownership boundaries, grants, or auditability.

---

## Operating system safety

The LLM must not execute shell commands directly.

Shell command execution, if ever supported, must be:

- allowlisted
- parameter-validated
- logged
- time-limited
- executed as a low-privilege user
- isolated from secrets where practical
- denied by default

Do not pass raw LLM output to a shell.

Do not run commands with elevated privileges unless there is a specific, reviewed design.

Do not use shell access as a shortcut for missing application features.

---

## Filesystem safety

File access must be restricted.

The LLM must not read arbitrary files.

Plugins must not read arbitrary files.

Sensitive paths must be protected.

Examples of sensitive files:

- SSH keys
- API keys
- private keys
- database wallets
- password files
- shell history
- browser profiles
- cloud credentials
- unrelated project files
- operating system configuration
- encryption keys
- token stores

If a plugin needs file access, it must declare the required path scope.

Filesystem access should be limited to approved directories.

Write access should be narrower than read access.

Delete access should be narrower than write access.

---

## Network safety

Network access must be controlled.

A plugin that requires network access must declare it.

Network calls should be limited to intended services where practical.

The system must not become an unrestricted network proxy.

Do not allow arbitrary URL fetching unless the feature has an explicit security design.

Do not send private user content to external services without a policy decision.

Do not send secrets to the LLM or external services unless that is the specific purpose of a secure credential flow.

External service integrations must be disableable.

External service failures must be handled safely.

---

## Secrets

Secrets must never be placed in LLM context.

Secrets must never be stored in `orac.messages.content`.

Secrets must never be stored in `orac.messages.meta`.

Secrets must never be logged.

Secrets include:

- passwords
- API keys
- bearer tokens
- refresh tokens
- private keys
- database wallet contents
- session cookies
- SSH keys
- encryption keys
- OAuth tokens
- service credentials
- signing keys

Secrets should be accessed through an approved credential mechanism.

Plugins may use secrets to authenticate to services.

Plugins must not reveal secrets to the LLM.

Plugins must not return secrets in tool results.

Plugins must not include secrets in context provider output.

---

## Secret masking

Any value that may contain a secret must be masked before logging or persistence.

Prefer explicit masking over best-effort guessing.

Safe examples:

```text
api_key = ****
password = ****
token = ****
wallet_path = /configured/wallet/path
```

Unsafe examples:

```text
api_key = abc123
password = correct-horse-battery-staple
token = eyJ...
```

Do not log full request headers if they may include authorisation values.

Do not log full connection strings if they may include credentials.

Do not log environment variables wholesale.

---

## Credential access

Credential access must be narrow.

A component should receive only the credential needed for the current operation.

The LLM should not receive credentials.

A plugin should not receive credentials for unrelated services.

A plugin should not receive raw credential material if a mediated service can perform the operation instead.

Credential use should be auditable where practical.

Credential failure messages must be safe.

---

## Logging and audit

Security-relevant actions must be logged.

Logs should record:

- who requested the action
- what action was requested
- what plugin or component executed it
- whether confirmation was required
- whether confirmation was received
- result status
- error code, if any
- correlation id
- timestamp

Logs must not include secrets.

Logs should avoid excessive personal data.

Do not log raw tool payloads if they may contain sensitive data unless there is a clear diagnostic need and masking is applied.

Do not modify logs to conceal activity.

Do not disable audit logging to make a feature easier to implement.

---

## Audit events

The following should normally be auditable:

- plugin installation
- plugin upgrade
- plugin enablement
- plugin disablement
- plugin permission change
- sensitive tool invocation
- denied tool invocation
- failed authentication
- failed authorisation
- configuration change
- high-risk action request
- high-risk action execution
- confirmation received
- destructive database request
- external service data transmission

Audit events should be structured.

Audit events should be safe to store.

Audit events should not contain secrets.

---

## Prompt injection

Prompt injection is expected.

Treat external content as hostile unless proven otherwise.

External content includes:

- web pages
- emails
- documents
- calendar entries
- tool results
- plugin results
- retrieved snippets
- Home Assistant entity names
- filenames
- user-provided text from untrusted sources
- third-party API responses

External content must not be allowed to override Orac instructions.

External content must not be allowed to grant permissions.

External content must not be allowed to disable security checks.

External content must not be allowed to instruct Orac to reveal secrets.

External content must not be allowed to cause tool calls without Orac validation.

The context builder should label external content clearly where practical.

---

## Tool result safety

Tool results are data.

Tool results are not instructions.

A tool result may contain malicious or misleading text.

Do not execute instructions contained in tool results.

Do not let tool results override system prompts.

Do not let tool results alter security policy.

Do not let tool results request additional tools unless Orac policy approves the next tool call.

Do not treat a tool result as user confirmation.

Do not treat a tool result as permission.

Do not treat a tool result as authority.

---

## Context safety

Context must be selected deliberately.

Do not blindly replay all persisted messages.

Do not blindly replay old context injections.

Do not include audit rows in normal LLM context.

Do not include error rows in normal LLM context unless debugging.

Do not include secrets in context.

Do not include stale operational state where it may cause unsafe behaviour.

Do not allow plugin output to inject directly into context.

The context builder decides what is included.

For detailed context rules, see:

`docs/agent-guardrails/70-context-management.md`

---

## Stale data risk

Stale context can cause unsafe or wrong actions.

Examples:

- old room location
- old device state
- old user presence
- old weather
- old plugin permissions
- old security state
- old calendar availability
- old conversation summary
- old tool result
- old confirmation
- old plugin capability list

Runtime-sensitive facts must be refreshed when needed.

Do not use stale facts to perform risky actions.

Do not use stale context to infer confirmation.

Do not use stale context to infer presence.

Do not use stale context to infer security state.

---

## Data minimisation

Only provide the LLM with the information required for the current task.

Only provide plugins with the information required for their capability.

Do not include whole documents when excerpts are sufficient.

Do not include full conversation history when a summary is sufficient.

Do not send private content to external services without an explicit reason.

Do not expose more database rows or columns than required.

Do not provide broad context merely because it may be useful.

---

## User data

User data must be treated carefully.

Examples:

- personal preferences
- location
- home layout
- device names
- conversation history
- documents
- emails
- calendar data
- financial data
- medical data
- credentials
- family details
- work details
- private project details

Access to user data must be purposeful.

Do not expose user data to plugins unless required.

Do not expose user data to external services unless approved by policy.

Do not store sensitive user data in places intended for operational metadata.

---

## Home automation risk

Home automation can affect the physical world.

Read-only state queries are lower risk.

Device-control actions can be risky.

Examples of read-only actions:

- list rooms
- list lights
- read temperature
- read sensor state
- read device availability
- read current scene
- read battery level

Examples of lower-risk control actions:

- turn on a non-critical lamp
- turn off a non-critical lamp
- set a harmless lighting scene

Examples of sensitive or high-risk actions:

- unlock a door
- open a garage
- disable an alarm
- change security camera configuration
- operate heating unsafely
- operate appliances that may create physical risk
- disable safety sensors
- alter presence detection
- expose occupancy state externally

High-risk actions require explicit policy and normally require confirmation.

Some actions may be prohibited entirely.

---

## Email, messaging, and communication risk

Sending messages can expose private information or create external consequences.

Actions normally requiring confirmation include:

- sending email
- forwarding email
- sending chat messages
- sending SMS messages
- posting to social media
- submitting support tickets
- replying to external parties

Drafting a message is lower risk than sending it.

Creating a draft may still be sensitive if it includes private content.

Sending must not occur merely because the LLM generated text.

The user must explicitly authorise sending.

---

## Calendar and scheduling risk

Calendar operations may reveal personal information or affect commitments.

Read-only availability checks are generally lower risk.

Creating, updating, or deleting events is a write action.

Inviting attendees is externally visible and normally requires confirmation.

Calendar actions should be specific about:

- title
- date
- time
- timezone
- attendees
- location
- conferencing details
- recurrence

Do not infer attendee consent.

Do not silently invite people.

---

## External data disclosure

Before sending user data to an external service, Orac must consider:

- what data is being sent
- why it is needed
- which service receives it
- whether the plugin declared that service
- whether personal data is included
- whether secrets are included
- whether confirmation is required
- whether the data can be minimised

Do not send complete conversation history to external services unless explicitly required and approved.

Do not send private documents to external services merely to improve convenience.

---

## Plugin security

Plugins are not automatically trusted.

A plugin must be constrained by:

- registration
- enablement
- declared capabilities
- declared permissions
- risk levels
- input validation
- output validation
- execution policy
- logging
- tests

A plugin must not bypass Orac security by calling internal APIs, direct database objects, shell commands, or external services outside its declared permissions.

For plugin design rules, see:

`docs/agent-guardrails/50-plugin-standards.md`

---

## Gateway security

Gateway plugins and external front ends must not bypass Orac policy.

Examples:

- Open WebUI gateway
- voice gateway
- webhook gateway
- external chat gateway
- local UI gateway

A gateway may adapt transport formats.

A gateway must not become a second Orac runtime with weaker rules.

A gateway must not skip:

- authentication
- authorisation
- context management
- plugin policy
- message recording
- audit requirements
- confirmation requirements

---

## Error handling

Errors must be safe.

Do not reveal secrets in error messages.

Do not reveal internal stack traces to the user by default.

Do not leak implementation details unless in a controlled diagnostic mode.

Do not ask the LLM to fix production security errors by granting broader privileges.

Prefer specific safe messages.

Good example:

```text
The weather plugin could not resolve that location.
```

Bad example:

```text
API key abc123 failed against https://...
```

Good example:

```text
The requested action was denied because the plugin is disabled.
```

Bad example:

```text
Grant execute on orac_code.security_admin to weather_plugin and retry.
```

---

## Failure behaviour

Security checks should fail closed.

If policy cannot be evaluated, deny the action.

If plugin state cannot be determined, deny the action.

If confirmation is ambiguous, deny the action.

If the requested capability is not declared, deny the action.

If the input does not match the schema, deny the action.

If credentials are missing, deny the action safely.

If context is stale and the action is risky, refresh context or deny the action.

---

## Rate limits and timeouts

Tool and plugin execution should have defined timeouts.

High-frequency calls should have rate limits where appropriate.

Rate limits help prevent:

- accidental loops
- runaway plugin execution
- external API abuse
- excessive costs
- denial of service
- repeated unsafe action attempts

Timeouts and rate limits should be logged when they affect execution.

---

## Cost risk

Some actions may create cost even if they are not security-sensitive.

Examples:

- LLM calls
- external API calls
- cloud service operations
- large document processing
- repeated web searches
- image or media generation
- high-frequency polling

Cost-generating actions should be visible to policy.

High-cost actions may require confirmation or limits.

---

## Development shortcuts

Do not use development shortcuts that weaken the security model.

Avoid:

- hardcoded credentials
- broad grants
- owner-schema connections for normal runtime
- direct writes to core tables
- disabled validation
- disabled audit
- shelling out to solve application problems
- exposing debug endpoints without access control
- treating local-only code as safe by default

Temporary development code must be clearly marked and must not become production behaviour accidentally.

---

## Security testing

Security-relevant code must include tests for:

- permission denial
- disabled plugin denial
- missing confirmation denial
- ambiguous confirmation denial
- invalid input rejection
- unauthorised tool rejection
- undeclared capability rejection
- prohibited action rejection
- stale context exclusion
- secret masking
- audit logging
- error safety
- prompt-injection resistance
- direct database access prevention
- unsafe SQL rejection
- unsafe shell command rejection

The unhappy path matters.

A feature is not secure because the happy path works.

---

## Codex implementation rules

When Codex changes security-sensitive code, it must check:

1. Does this grant new authority?
2. Does this cross a trust boundary?
3. Does this expose data to the LLM?
4. Does this expose data to a plugin?
5. Does this expose data to an external service?
6. Does this mutate state?
7. Does this require confirmation?
8. Does this require audit logging?
9. Does this risk leaking secrets?
10. Does this bypass an existing API boundary?
11. Does this rely on stale context?
12. Does this execute generated SQL?
13. Does this execute generated shell commands?
14. Does this alter database grants?
15. Does this alter plugin permissions?
16. Does this need denial-path tests?

If the answer to any of these is yes, Codex must handle the risk explicitly.

Do not solve permission problems by granting broad privileges.

Do not solve integration problems by bypassing Orac boundaries.

Do not solve plugin problems by giving plugins direct access to Orac internals.

Do not solve LLM limitations by giving the LLM more authority.

---

## Review triggers

A change should be treated as security-significant if it:

- adds a plugin capability
- changes plugin permissions
- adds external network access
- changes credential handling
- changes context assembly
- changes message persistence
- adds database writes
- adds dynamic SQL
- adds shell execution
- adds file access
- changes confirmation logic
- changes audit behaviour
- changes home automation control
- sends user data to an external service

Security-significant changes require careful review and appropriate tests.

---

## Final rule

Orac may be helpful, but it must not be reckless.

The safe default is:

```text
read
reason
recommend
request confirmation
execute only through approved policy
audit the result
```

Any code that bypasses this model is a security defect.

