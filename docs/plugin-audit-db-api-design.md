# Plugin Audit DB/API Design

This document defines the database/API design for first-class plugin
audit/result persistence. It follows the current Orac object-by-object schema
layout.

## Decision

Database DDL/API assets are now represented as object-by-object files. Runtime
plugin execution is wired to these objects through a narrow Orac-owned audit
adapter; plugin code still does not write audit records directly.

Boundary decisions:

- `resources/db/schema/AGENT_CONTEXT.md` requires the normal Orac flow:
  `orac_core -> orac_api -> orac_code -> orac`.
- Current table, constraint, index, TAPI, grant, and install-order conventions
  are object-by-object.
- `docs/agent-guardrails/table-abbreviations.csv` records the approved
  abbreviations for the plugin audit tables.
- Runtime callers should use `orac_code.plugin_audit_api`; plugin code should
  not write audit records directly.

## Approved Table Abbreviations

The following entries are recorded in
`docs/agent-guardrails/table-abbreviations.csv` and are used by the current
object-by-object plugin audit assets:

| Schema | Table | Abbreviation |
| --- | --- | --- |
| `orac_core` | `plugin_invocations` | `plg_inv` |
| `orac_core` | `plugin_audit_events` | `plg_audevt` |

These abbreviations should be used for derived object names such as primary
keys, foreign keys, check constraints, indexes, triggers, and generated TAPI
objects where table abbreviations are part of the existing naming convention.

## Current Tables

The two core tables already exist as object-by-object assets. The notes below
document their current shape and the remaining runtime integration boundary.

### `orac_core.plugin_invocations`

One row per plugin invocation attempt or policy-stopped plugin action.

This is the durable summary row used by Orac runtime, APEX, and reporting. It
should be created as a normal `orac_core` table with standard audit columns and
`row_version`.

Suggested columns:

| Column | Purpose |
| --- | --- |
| `plugin_invocation_id` | Identity primary key. |
| `conversation_id` | Nullable FK to `orac_core.conversations`. |
| `message_id` | Nullable FK to the persisted `orac_core.messages` row most closely associated with the plugin decision or result. |
| `user_id` | Nullable FK to `orac_core.users` when available. |
| `request_id` | Protocol request id, for example `req_*`. |
| `correlation_id` | Cross-component correlation id when available. |
| `turn_id` | Voice/display turn id when available. |
| `plugin_id` | Stable plugin id from manifest. |
| `plugin_name` | Plugin display name at invocation time. |
| `action_type` | Execution policy action type. |
| `capabilities` | JSON array of declared capabilities considered. |
| `entitlements` | JSON array of declared entitlements considered. |
| `policy_decision` | `allowed`, `denied`, or `requires_confirmation`. |
| `policy_reason` | Safe policy reason where relevant. |
| `confirmation_id` | Broker-issued confirmation id where relevant. |
| `confirmation_status` | `issued`, `accepted`, `rejected`, `expired`, `replayed`, `replay_rejected`, `mismatched`, `missing`, or `pending`. |
| `execution_status` | Final summary status. |
| `timeout_seconds` | Configured timeout when relevant. |
| `failure_type` | Safe failure category. |
| `failure_message` | Safe failure summary, not a stack trace. |
| `provenance_json` | JSON snapshot of Orac-owned plugin provenance. |
| `created_on` | Standard creation timestamp. |
| `created_by` | Standard creator. |
| `updated_on` | Standard update timestamp. |
| `updated_by` | Standard updater. |
| `row_version` | Standard optimistic locking value. |

Suggested `execution_status` values:

- `candidate_selected`
- `policy_evaluated`
- `confirmation_required`
- `confirmation_issued`
- `confirmation_accepted`
- `confirmation_rejected`
- `confirmation_expired`
- `confirmation_replay_rejected`
- `confirmation_mismatched`
- `execution_started`
- `completed`
- `failed`
- `timed_out`
- `denied`

The first database implementation may store a single final summary row per
invocation and rely on `plugin_audit_events` for the detailed lifecycle.

### `orac_core.plugin_audit_events`

Append-only event stream for plugin lifecycle transitions.

This table records security-relevant transitions even when no plugin code is
executed. It should reference `plugin_invocations` and optionally snapshot the
event payload as JSON.

Suggested columns:

| Column | Purpose |
| --- | --- |
| `plugin_audit_event_id` | Identity primary key. |
| `plugin_invocation_id` | FK to `orac_core.plugin_invocations`. |
| `event_type` | Lifecycle event name. |
| `event_status` | Event-local status. |
| `event_message` | Safe event message. |
| `policy_decision` | Policy decision associated with this event where relevant. |
| `confirmation_id` | Broker-issued confirmation id where relevant. |
| `execution_status` | Execution status associated with this event where relevant. |
| `failure_type` | Safe failure category where relevant. |
| `failure_message` | Safe failure summary where relevant. |
| `event_payload_json` | JSON event payload/provenance snapshot. |
| `created_on` | Standard event timestamp. |
| `created_by` | Standard creator. |
| `updated_on` | Standard update timestamp if an administrative correction is ever required. |
| `updated_by` | Standard updater if an administrative correction is ever required. |
| `row_version` | Standard optimistic locking value, if kept consistent with current table style. |

Suggested `event_type` values:

- `candidate_selected`
- `policy_evaluated`
- `confirmation_required`
- `confirmation_issued`
- `confirmation_accepted`
- `confirmation_rejected`
- `confirmation_expired`
- `confirmation_replay_rejected`
- `confirmation_mismatched`
- `execution_started`
- `execution_completed`
- `execution_failed`
- `execution_timed_out`

## Object-by-Object Implementation Shape

The object files already exist in the current style.

Core layer:

- `resources/db/schema/orac_core/table/plugin_invocations.sql`
- `resources/db/schema/orac_core/table/plugin_audit_events.sql`
- `resources/db/schema/orac_core/index/plg_inv_pk.sql`
- `resources/db/schema/orac_core/index/plg_audevt_pk.sql`
- `resources/db/schema/orac_core/index/<approved_abbrev>_<fk>_idx.sql`
- `resources/db/schema/orac_core/constraint_pk/plg_inv_pk.sql`
- `resources/db/schema/orac_core/constraint_pk/plg_audevt_pk.sql`
- `resources/db/schema/orac_core/constraint_fk/<approved_abbrev>_<target>_fk1.sql`
- `resources/db/schema/orac_core/constraint_other/<approved_abbrev>_ck*.sql`
- `resources/db/schema/orac_core/comment/plugin_invocations.sql`
- `resources/db/schema/orac_core/comment/plugin_audit_events.sql`
- `resources/db/schema/orac_core/trigger/plg_inv_bu.sql`
- `resources/db/schema/orac_core/trigger/plg_audevt_bu.sql`

API layer:

- `resources/db/schema/orac_api/view/plugin_invocations_v.sql`
- `resources/db/schema/orac_api/view/plugin_audit_events_v.sql`
- `resources/db/schema/orac_api/package_spec/plugin_invocations_tapi.sql`
- `resources/db/schema/orac_api/package_body/plugin_invocations_tapi.sql`
- `resources/db/schema/orac_api/package_spec/plugin_audit_events_tapi.sql`
- `resources/db/schema/orac_api/package_body/plugin_audit_events_tapi.sql`

Code layer:

- `resources/db/schema/orac_code/package_spec/plugin_audit_api.sql`
- `resources/db/schema/orac_code/package_body/plugin_audit_api.sql`

Grant updates:

- grant core table DML to `orac_api` with grant option;
- grant API views/TAPIs to `orac_code`;
- grant `execute` on `orac_code.plugin_audit_api` to `orac`;
- avoid granting direct `orac_core` table access to runtime, APEX, or plugin
  bridge schemas.

Install ordering:

1. core tables;
2. indexes;
3. primary keys;
4. unique/check constraints;
5. foreign keys;
6. comments;
7. triggers;
8. API views;
9. API TAPIs;
10. code package;
11. grants and synonyms where explicitly required.

## API Package Contract

`orac_code.plugin_audit_api` should be the runtime-facing interface. Runtime
code should not insert into `orac_api` views directly.

Implemented procedures:

```sql
procedure begin_invocation(
  p_plugin_invocation_id out number,
  p_row_version          out number,
  p_plugin_id            in  varchar2,
  p_plugin_name          in  varchar2,
  p_action_type          in  varchar2,
  p_request_id           in  varchar2 default null,
  p_correlation_id       in  varchar2 default null,
  p_turn_id              in  varchar2 default null,
  p_conversation_id      in  number default null,
  p_message_id           in  number default null,
  p_user_id              in  number default null,
  p_capabilities         in  json default null,
  p_entitlements         in  json default null,
  p_provenance_json      in  json default null
);
```

```sql
procedure record_policy_decision(
  p_plugin_invocation_id in number,
  p_policy_decision      in varchar2,
  p_policy_reason        in varchar2 default null,
  p_event_message        in varchar2 default null,
  p_provenance_json      in json default null,
  p_row_version          out number
);
```

```sql
procedure record_confirmation_event(
  p_plugin_invocation_id in number,
  p_event_type           in varchar2,
  p_confirmation_id      in varchar2,
  p_confirmation_status  in varchar2,
  p_event_message        in varchar2 default null,
  p_event_payload_json   in json default null,
  p_row_version          out number
);
```

```sql
procedure record_execution_event(
  p_plugin_invocation_id in number,
  p_event_type           in varchar2,
  p_execution_status     in varchar2,
  p_timeout_seconds      in number default null,
  p_failure_type         in varchar2 default null,
  p_failure_message      in varchar2 default null,
  p_provenance_json      in json default null,
  p_row_version          out number
);
```

```sql
procedure link_message(
  p_plugin_invocation_id in number,
  p_message_id           in number,
  p_row_version          out number
);
```

The API package should:

- insert or update only through `orac_api` views/TAPIs;
- create one event row for every procedure call that represents a lifecycle
  transition;
- update the invocation summary row with the latest safe status;
- reject unknown lifecycle/status values using check constraints or package
  validation;
- never persist raw stack traces or secrets.

## Relationship to Conversation and Message Records

The plugin audit model should relate to existing conversation state without
becoming conversation history itself.

Recommended relationships:

- `plugin_invocations.conversation_id` nullable FK to `orac_core.conversations`;
- `plugin_invocations.message_id` nullable FK to `orac_core.messages`;
- `plugin_invocations.user_id` nullable FK to `orac_core.users`;
- event rows FK to `plugin_invocations`.

Plugin audit rows should not replace `messages`. Current assistant-turn
metadata can continue to carry provenance for backwards compatibility. The
first runtime persistence integration should write both:

- normal assistant/tool-visible text through the existing message path;
- first-class plugin audit/result rows through `plugin_audit_api`.

## Mapping from Current Provenance

Current `PluginExecutionResult.provenance` maps as follows:

| Provenance key | Target field |
| --- | --- |
| `source` | `provenance.source` snapshot, not a core status field. |
| `plugin_id` | `plugin_invocations.plugin_id`. |
| `plugin_name` | `plugin_invocations.plugin_name`. |
| `action_type` | `plugin_invocations.action_type`. |
| `capabilities` | `plugin_invocations.capabilities`. |
| `entitlements` | `plugin_invocations.entitlements`. |
| `status = allowed` | `policy_decision = allowed`; execution result later decides `completed`. |
| `status = denied` | `policy_decision = denied`; `execution_status = denied`. |
| `status = requires_confirmation` | `policy_decision = requires_confirmation`; `execution_status = confirmation_required`. |
| `status = failed` | `policy_decision = allowed`; `execution_status = failed`. |
| `status = timed_out` | `policy_decision = allowed`; `execution_status = timed_out`. |
| `policy_decision` | `plugin_invocations.policy_decision` when present. |
| `confirmation.confirmation_id` | `plugin_invocations.confirmation_id`. |
| `confirmation.status` | `plugin_invocations.confirmation_status`. |
| `confirmation.trusted` | retained in `plugin_invocations.provenance_json` until a dedicated trusted-confirmation column is added. |
| `confirmation_request.confirmation_id` | pending `confirmation_id`. |
| `timeout_seconds` | `plugin_invocations.timeout_seconds`. |
| `failure_type` | `plugin_invocations.failure_type`. |
| `failure_message` | `plugin_invocations.failure_message`. |
| `scaffold` | retained in `plugin_invocations.provenance_json`. |
| whole provenance dict | `plugin_invocations.provenance_json` and relevant event payloads. |

## Home Assistant Boundary

Home Assistant remains scaffold-only. This audit model is required before HA
device control can be considered, but it does not enable HA runtime behavior.

The existing `orac_ha` tables remain cache/state tables:

- `ha_areas`
- `ha_devices`
- `ha_entities`
- `ha_states_current`

They should not store plugin audit or device-control audit records.

## Deferred Work

- Add database/static verification for the existing object-by-object assets.
- Add Python runtime persistence through `orac_code.plugin_audit_api`.
- Backfill or correlate existing assistant-turn provenance where useful.
- Persist trusted confirmation broker state.
- Implement read-only Home Assistant cache population in a separate pass.
- Keep real Home Assistant control disabled until audit, confirmation,
  credentials, entitlements, state freshness, and safety semantics are complete.
