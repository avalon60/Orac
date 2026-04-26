# Context Management

## Purpose

This document defines how Orac manages conversation context.

It covers:

- how persisted messages are interpreted
- how runtime LLM context is assembled
- how `role` and `message_type` must be used
- how tool/plugin results enter context
- how stale context is avoided
- how context-window pressure is handled

The `orac.messages` table is a durable record of conversation events.

The LLM context window is a temporary runtime projection.

These are not the same thing.

Persisted history records what happened.

Runtime context contains only what the model needs for the current turn.

---

## Core principle

Never treat the contents of `orac.messages` as the exact prompt to send to the model.

The prompt must be assembled deliberately.

The context builder is responsible for selecting, ordering, summarising, transforming, or excluding persisted rows.

---

## Message column responsibilities

The columns `role` and `message_type` must remain strictly separated.

### `role`

`role` defines the LLM-facing actor.

Allowed values:

```sql
'system'
'user'
'assistant'
'tool'
````

`role` answers:

> Who or what should the LLM see this message as coming from?

### `message_type`

`message_type` defines the semantic purpose of the row.

Allowed values:

```sql
'chat'
'system_prompt'
'context_injection'
'tool_call'
'tool_result'
'summary'
'error'
'audit'
```

`message_type` answers:

> Why does this row exist, and how should Orac treat it?

---

## Non-negotiable rules

Do not use `role` to describe message purpose.

Do not use `message_type` to describe the speaker.

Do not add `plugin` as a role.

Do not use plugin names as roles.

Do not use plugin names as message types.

Incorrect:

```text
role = 'plugin'
message_type = 'weather'
```

Correct:

```text
role = 'tool'
message_type = 'tool_result'
plugin_id = <weather plugin id>
```

Correct:

```text
role = 'system'
message_type = 'context_injection'
plugin_id = <home assistant plugin id>
```

A plugin is provenance, not a role.

---

## Standard role and message_type combinations

Use the following combinations unless there is a deliberate, documented model change.

| role        | message_type        | Meaning                                            |
| ----------- | ------------------- | -------------------------------------------------- |
| `user`      | `chat`              | Normal user input.                                 |
| `assistant` | `chat`              | Final or intermediate assistant text.              |
| `system`    | `system_prompt`     | Base instruction, policy, or operating prompt.     |
| `system`    | `context_injection` | Runtime context injected by Orac.                  |
| `assistant` | `tool_call`         | Assistant or Orac request to invoke a tool/plugin. |
| `tool`      | `tool_result`       | Result returned by a tool/plugin.                  |
| `system`    | `summary`           | Summary used as future context.                    |
| `system`    | `error`             | Operational error record.                          |
| `system`    | `audit`             | Internal audit/debug record.                       |

Avoid invalid combinations such as:

```text
role = 'tool', message_type = 'chat'
role = 'assistant', message_type = 'tool_result'
role = 'user', message_type = 'tool_result'
role = 'system', message_type = 'chat'
```

---

## Context visibility by message_type

The context builder must not include all rows blindly.

Default visibility rules:

| message_type        | Default future LLM visibility                                              |
| ------------------- | -------------------------------------------------------------------------- |
| `chat`              | Yes, subject to window limits and relevance.                               |
| `system_prompt`     | Yes, if active.                                                            |
| `context_injection` | Only for the intended turn or while explicitly valid.                      |
| `tool_call`         | Only during the active tool-resolution loop, unless deliberately replayed. |
| `tool_result`       | Only during the active tool-resolution loop, unless deliberately replayed. |
| `summary`           | Yes, if selected by context policy.                                        |
| `error`             | No, unless explicitly needed for troubleshooting.                          |
| `audit`             | No.                                                                        |

The default must be conservative.

Rows are included because they are useful, not because they exist.

---

## Context assembly order

A normal LLM request should be assembled in this broad order:

1. Active system prompt.
2. Current operating guardrails.
3. Current runtime context injections.
4. Relevant summaries.
5. Selected recent conversation history.
6. Current user message.
7. Active tool call and tool result rows, if resolving a tool loop.

Do not use raw insertion order as the only assembly strategy.

Do not let old runtime context outrank the current user message.

Do not let historical tool traces dominate the current prompt.

---

## System prompt rows

Rows with:

```text
role = 'system'
message_type = 'system_prompt'
```

represent durable or configured behavioural instructions.

They may include:

* Orac identity
* safety rules
* tool-use rules
* response-format rules
* model-specific operating instructions

Only active system prompts should be included.

Superseded system prompts must not be replayed merely because they are present in message history.

---

## Context injection rows

Rows with:

```text
role = 'system'
message_type = 'context_injection'
```

represent runtime context supplied by Orac.

Examples:

* current room
* current device location
* current user preference
* available Home Assistant entities
* current weather facts
* relevant memory
* selected plugin capability descriptions
* retrieved document snippets

Context injections are often perishable.

They must be treated as scoped context, not permanent truth.

A context injection should have enough metadata to determine:

* source
* creation time
* intended turn
* expiry or validity
* plugin provenance, if applicable

Old context injections must not be blindly replayed.

---

## Tool calls and tool results

A tool call is recorded as:

```text
role = 'assistant'
message_type = 'tool_call'
```

A tool result is recorded as:

```text
role = 'tool'
message_type = 'tool_result'
```

The tool result is evidence for the assistant.

The user-facing answer is normally a later row:

```text
role = 'assistant'
message_type = 'chat'
```

Do not treat raw tool output as the final assistant response unless the tool result is intentionally exposed.

Tool traces should usually be visible only during the active turn.

Later turns should use summaries or derived facts where appropriate.

---

## Plugin provenance

Plugin involvement must be tracked separately from role and message_type.

Preferred fields include:

```text
plugin_id
tool_name
tool_call_id
llm_id
meta
```

The plugin is the source or executor.

The plugin is not the conversational role.

For example:

```text
role = 'tool'
message_type = 'tool_result'
plugin_id = 3
tool_name = 'weather.current'
```

or:

```text
role = 'system'
message_type = 'context_injection'
plugin_id = 7
tool_name = 'home_assistant.area_context'
```

---

## Content and meta

Use `content` for the actual payload.

Use `meta` for operational metadata.

The context builder may include `content`.

The context builder must not expose `meta` to the LLM unless there is an explicit rule allowing it.

Examples of `content`:

```json
{
  "format": "text",
  "text": "The user is currently in the kitchen."
}
```

```json
{
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

Examples of `meta`:

```json
{
  "source": "weather_plugin",
  "plugin_id": 3,
  "duration_ms": 212,
  "cache_hit": false
}
```

Do not store user-visible answer text only in `meta`.

Do not rely on `meta` for normal model-visible content.

---

## Turn handling

A turn may contain multiple message rows.

Example:

| turn_index | role        | message_type        |
| ---------: | ----------- | ------------------- |
|         12 | `user`      | `chat`              |
|         12 | `system`    | `context_injection` |
|         12 | `assistant` | `tool_call`         |
|         12 | `tool`      | `tool_result`       |
|         12 | `assistant` | `chat`              |

Do not assume one turn equals one message row.

When reconstructing order, use:

```sql
order by
  turn_index,
  message_id
```

If exact intra-turn sequencing becomes critical, add a dedicated sequence column rather than overloading `message_type`.

---

## Context-window management

The context window is finite.

The context builder must actively manage it.

The following content should normally have priority:

1. Active system prompt and guardrails.
2. Current user message.
3. Current runtime context required to answer the user.
4. Current tool results required for the active turn.
5. Durable user preferences relevant to the request.
6. Recent conversation history.
7. Older summaries.
8. Older raw conversation history.
9. Historical tool traces.

When context pressure is high, prefer summaries over raw old messages.

Do not discard active system instructions.

Do not discard the current user message.

Do not include low-value historical tool traces when a summary will do.

---

## Summarisation

Summaries should be stored as:

```text
role = 'system'
message_type = 'summary'
```

A summary is not a normal assistant reply.

A summary is a compact context artifact.

Summaries should preserve:

* decisions made
* user preferences
* project terminology
* unresolved questions
* current design direction
* important constraints
* agreed rules

Summaries should not preserve:

* irrelevant banter
* stale plugin output
* transient device state
* one-off weather results
* old tool traces unless they explain an important decision

---

## Stale context

The context builder must avoid stale context.

Examples of stale context:

* old weather
* old room location
* old device state
* old presence data
* old plugin capability lists
* superseded system prompts
* obsolete project decisions

Stale context should be regenerated, summarised, or excluded.

Never assume a persisted `context_injection` row is still true.

---

## Audit and error rows

Rows with:

```text
message_type = 'audit'
```

or:

```text
message_type = 'error'
```

are not normal model context.

They are operational records.

They should only be included in an LLM request when explicitly debugging or when a controlled diagnostic workflow requires it.

Do not leak internal errors into normal assistant responses.

---

## Implementation guidance for Codex

When writing code that inserts into `orac.messages`, follow this decision process.

### Step 1: Choose role

Ask:

> What role should the LLM see this as?

Use only:

```text
system
user
assistant
tool
```

### Step 2: Choose message_type

Ask:

> Why does this row exist?

Use only:

```text
chat
system_prompt
context_injection
tool_call
tool_result
summary
error
audit
```

### Step 3: Record provenance

Ask:

> Where did this come from?

Use fields such as:

```text
plugin_id
tool_name
tool_call_id
llm_id
meta
```

Do not encode provenance in `role`.

Do not encode provenance in `message_type`.

### Step 4: Decide future visibility

Ask:

> Should this row ever be included in future model context?

If yes, the context builder must include it deliberately.

If no, it remains persisted history only.

### Step 5: Do not invent values

If a new role or message_type appears necessary, stop.

Update the guardrail documentation, constraints, context builder, and tests deliberately.

Do not introduce ad-hoc values from application code.

---

## Recommended database constraints

The message role should be constrained:

```sql
alter table orac.messages add constraint messages_role_ck
  check (
    role in (
      'system',
      'user',
      'assistant',
      'tool'
    )
  );
```

The message type should be constrained:

```sql
alter table orac.messages add constraint messages_message_type_ck
  check (
    message_type in (
      'chat',
      'system_prompt',
      'context_injection',
      'tool_call',
      'tool_result',
      'summary',
      'error',
      'audit'
    )
  );
```

The allowed combinations should also be constrained:

```sql
alter table orac.messages add constraint messages_role_type_ck
  check (
    (
      role = 'user'
      and message_type in (
        'chat'
      )
    )
    or
    (
      role = 'assistant'
      and message_type in (
        'chat',
        'tool_call'
      )
    )
    or
    (
      role = 'tool'
      and message_type in (
        'tool_result'
      )
    )
    or
    (
      role = 'system'
      and message_type in (
        'system_prompt',
        'context_injection',
        'summary',
        'error',
        'audit'
      )
    )
  );
```

These constraints are intentionally strict.

Changing them should be treated as an architectural decision.

---

## Required tests

Any implementation touching context management must include tests for:

* valid role values
* valid message_type values
* invalid role/message_type combinations
* normal user and assistant chat rows
* tool call and tool result rows
* plugin-sourced context injection
* exclusion of `audit` rows from normal context
* exclusion of `error` rows from normal context
* stale context injection handling
* context-window trimming
* summary selection
* ordering by `turn_index` and `message_id`

---

## Final rule

Every message row must satisfy this model:

```text
role         = how the LLM should see the speaker
message_type = why this row exists
plugin_id    = which plugin was involved, if any
content      = the actual payload
meta         = operational metadata
```

Any code that blurs these responsibilities is a design bug.


