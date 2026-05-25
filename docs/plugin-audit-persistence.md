# Plugin Audit Persistence

This note defines the target persistence boundary for plugin invocation audit
and result records. It is a design document, not a database migration.

The concrete database/API design is in
`docs/plugin-audit-db-api-design.md`.

## Purpose

Plugin results currently flow through response metadata and assistant-turn
metadata as provenance. That is still useful for compatibility, and Orac now
normalises that provenance through a narrow runtime audit adapter before it
reaches the approved database API.

The target model is a first-class plugin audit/result record owned by Orac core.
Plugin code must not write these records directly.

## Lifecycle

The durable audit stream should be able to represent these lifecycle points:

1. Plugin candidate selected.
2. Policy evaluated.
3. Confirmation required.
4. Confirmation request issued.
5. Confirmation accepted, rejected, expired, replayed, or mismatched.
6. Plugin execution started.
7. Plugin execution completed.
8. Plugin execution failed.
9. Plugin execution timed out.

Not every invocation needs a separate row for every point in the first database
version. A conservative initial table can store one row per final invocation
outcome, with status fields that identify the lifecycle point reached.

## Minimum Durable Fields

The first durable plugin audit/result model should store:

| Field | Purpose |
| --- | --- |
| `plugin_audit_id` | Surrogate primary key for the audit row. |
| `conversation_id` | Conversation that produced the plugin decision/result. |
| `user_id` | Stable Orac user identifier if available. |
| `message_id` | Persisted message id if available. |
| `request_id` | Protocol request id or equivalent correlation id. |
| `turn_id` | Voice/display turn id when available. |
| `correlation_id` | Cross-system correlation id when available. |
| `route` | Protocol route, for example `orac.prompt`. |
| `plugin_id` | Stable plugin identifier. |
| `plugin_name` | Display name at execution time. |
| `action_type` | Execution policy action type. |
| `capabilities` | Declared capabilities considered for the action. |
| `entitlements` | Declared entitlements considered for the action. |
| `policy_decision` | `allowed`, `denied`, or `requires_confirmation`. |
| `confirmation_required` | Whether policy required confirmation. |
| `confirmation_id` | Broker-issued confirmation id where relevant. |
| `confirmation_status` | Broker validation status where relevant. |
| `confirmation_trusted` | Whether the confirmation was broker-trusted. |
| `execution_status` | `completed`, `denied`, `confirmation_required`, `failed`, or `timed_out`. |
| `timeout_seconds` | Configured timeout for timed-out executions. |
| `failure_type` | Safe failure category, not a stack trace. |
| `failure_message` | Safe failure summary suitable for metadata/audit. |
| `scaffold` | Whether the manifest was scaffold/experimental. |
| `provenance_json` | Core-owned provenance snapshot for forward compatibility. |
| `created_at` | Row creation timestamp. |
| `updated_at` | Last status update timestamp if rows are updated in place. |

## Current Metadata Mapping

Current response metadata:

- `meta.source` maps to audit `source`.
- `meta.provenance.plugin_id` maps to audit `plugin_id`.
- `meta.provenance.plugin_name` maps to audit `plugin_name`.
- `meta.provenance.action_type` maps to audit `action_type`.
- `meta.provenance.status` maps to audit `execution_status`.
- `meta.provenance.policy_decision` maps to audit `policy_decision`.
- `meta.provenance.confirmation` and `confirmation_request` map to the
  confirmation fields.
- `meta.provenance.failure_type`, `failure_message`, and `timeout_seconds` map
  to failure/timeout fields.

Current assistant-turn metadata:

- `meta.source` identifies plugin-originated assistant text.
- `meta.plugin_id` maps to audit `plugin_id`.
- `meta.plugin_status` maps to audit `execution_status`.
- `meta.provenance` is the source snapshot for the audit normalizer.

The current runtime continues writing this metadata exactly as it does today,
and the audit adapter maps it onto the durable plugin audit tables without
changing plugin behaviour or direct response metadata.

## Database Recommendation

The object-by-object database/API assets now provide:

- `ORAC_CORE` plugin audit/result tables;
- `ORAC_API` views and TAPIs for controlled inserts/updates;
- an `ORAC_CODE` caller path for the Orac runtime;
- no direct plugin access to audit tables.

Do not store raw Python stack traces in user-visible columns. Developer logs may
carry diagnostics, but durable audit should store only safe failure type and
message fields plus a structured provenance snapshot.

## Deferred

- Migration/backfill from existing assistant-turn provenance metadata.
- Durable confirmation broker state.
- Full confirmation UI/protocol workflow.
- Process-isolated plugin execution and hard cancellation.
- Real Home Assistant device control.
