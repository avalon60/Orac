# RAG Usage Privileges

RAG usage privileges are Oracle-maintained historical `USE` grants from a
registered Orac principal to a canonical project or plugin knowledge scope.
Authentication establishes the exact case-preserving username; authorization
resolves it to an active `orac_core.users` row. Aliases never grant authority.

## Administration API

Use `orac_code.rag_usage_privilege_api` from an approved administrative schema:

```sql
select orac_code.rag_usage_privilege_api.grant_scope_usage(
         p_username          => 'clive',
         p_scope_type        => 'PLUGIN',
         p_scope_key         => 'drop_box',
         p_granted_by        => 'LOCAL_ACCEPTANCE',
         p_grant_reason_code => 'LOCAL_ACCEPTANCE'
       ) result
  from dual;

select orac_code.rag_usage_privilege_api.revoke_scope_usage(
         p_username           => 'clive',
         p_scope_type         => 'PLUGIN',
         p_scope_key          => 'drop_box',
         p_revoked_by         => 'LOCAL_ACCEPTANCE',
         p_revoke_reason_code => 'LOCAL_ACCEPTANCE'
       ) result
  from dual;
```

Duplicate effective grants return `RAG_USAGE_ALREADY_GRANTED`. Revocation
updates stored state and preserves history. Re-grant after revocation inserts a
new row. Re-grant after expiry first closes the expired stored-active row with
reason `EXPIRED`, then inserts a new row. The unique index uses only stored
`active_yn`; it contains no current-time expression.

## Dependency and lifecycle matrix

All Oracle foreign keys below are no-cascade. A database guard permanently
blocks hard deletion of every project, plugin, and canonical scope even when
ordinary child rows have been removed.

| Parent object | Dependent object | Current relationship | Current enforcement | New enforcement | Delete behaviour | Deactivation behaviour | Migration or backfill |
|---|---|---|---|---|---|---|---|
| `orac_core.project_registry` | `knowledge_scopes` and all indirectly project-owned corpus/history | `project_id` | Previously only string scope conventions | `KN_SCOPE_PROJECT_FK`, one-scope uniqueness, atomic API synchronisation, immutable project code, `PRJREG_BD` guard | Project hard delete always rejected | Scope, privileges, configuration, and corpus remain; inactive project retrieval is unavailable | Exactly one scope created per existing project; invalid or ambiguous rows halt |
| `orac_core.plugin_registry` | `knowledge_scopes` | `plugin_registry_id` | Previously only string scope conventions | `KN_SCOPE_PLUGIN_FK`, one-scope uniqueness, atomic upsert synchronisation, immutable plugin id, `PLGREG_BD` guard | Plugin hard delete always rejected | Scope and privilege history remain; shared plugin eligibility makes retrieval unavailable | Exactly one scope created per existing plugin; invalid or ambiguous rows halt |
| `orac_core.plugin_registry` | `plugin_services` | `plugin_registry_id` for plugin-owned services; Core is synthetic | Previously `plugin_id` string only | `PLGSVC_REGISTRY_FK`, `service_owner_type`, owner XOR check, BIU identity validation | Registry guard rejects parent delete; child FK is final relational boundary | Service row and history remain; runtime eligibility follows the registry policy | Real plugins resolve exactly; `orac_core` maps to `CORE`; unexplained rows halt |
| `orac_core.plugin_registry` | `plugin_apex_apps`, `plugin_db_deployments`, `plugin_invocations` | Immutable `plugin_id` historical snapshot | String identity and application APIs; no registry FK | Permanent registry delete guard plus immutable identifier; deliberately no new history-to-current-registration FK | Plugin hard delete always rejected | Applications, deployments, invocations, and audit history remain | No history rewrite or guessed registry ownership |
| `orac_core.users` | `rag_usage_privileges` | `user_id` | Previously INI username lookup | `RAG_USEPRV_USER_FK`, active-user API checks, trimmed username constraint/trigger | Referenced user delete is rejected by FK | Inactive principal is denied; privilege history remains | No user-specific privileges seeded |
| `orac_core.knowledge_scopes` | `rag_usage_privileges` | `knowledge_scope_id` | Previously INI `TYPE:key` entries | `RAG_USEPRV_SCOPE_FK`, deterministic active-grant index, `KN_SCOPE_BD` guard | Scope hard delete always rejected | Privilege history remains; parent status controls availability | Privilege table starts empty; local acceptance grants use API only |
| `orac_core.knowledge_scopes` | `knowledge_source_objects` | `knowledge_scope_id` on the sole authoritative corpus owner | Previously type/key strings on source and document | `KN_SRCOBJ_SCOPE_FK`; compatibility values are derived through views | Scope guard and FK reject deletion | Corpus remains; inactive parent makes retrieval unavailable | Exact string-to-scope backfill; unknown/ambiguous strings halt |
| `knowledge_source_objects` | `knowledge_documents` | `source_object_id` | Existing `KN_DOC_KN_SRCOBJ_FK1` | Preserved; document scope now derives through the source | Parent delete rejected while documents exist | Lineage remains | IDs unchanged; duplicate document scope columns removed |
| `knowledge_source_objects` | `knowledge_document_versions`, `knowledge_ingestion_requests` | `source_object_id` | Existing `KN_DOCVER_KN_SRCOBJ_FK1`, `KN_INGREQ_KN_SRCOBJ_FK1` | Preserved | Parent delete rejected while history exists | History remains | Existing IDs and lineage preserved |
| `knowledge_documents` | `knowledge_document_versions`, `knowledge_ingestion_requests` | `document_id`; current-version back-reference | Existing `KN_DOCVER_KN_DOC_FK1`, `KN_INGREQ_KN_DOC_FK1`, `KN_DOC_KN_DOCVER_FK1` | Preserved | Delete rejected while versions, current version, or requests exist | History remains | No row rewrite |
| `knowledge_document_versions` | `knowledge_extractions`, `knowledge_ingestion_requests` | `document_version_id` | Existing `KN_EXT_KN_DOCVER_FK1`, `KN_INGREQ_KN_DOCVER_FK1` | Preserved | Delete rejected while extraction/request history exists | History remains | No row rewrite |
| `knowledge_extractions` | `knowledge_chunk_sets` | `extraction_id` | Existing `KN_CHSET_KN_EXT_FK1` | Preserved | Delete rejected while chunk sets exist | History remains | No row rewrite |
| `knowledge_chunk_sets` | `knowledge_chunks` | `chunk_set_id` | Existing `KN_CHNK_KN_CHSET_FK1` | Preserved | Delete rejected while chunks exist | History remains | No row rewrite |
| `knowledge_chunks` | `knowledge_chunk_embeddings` | `knowledge_chunk_id` | Existing `KN_CHNKEMB_KN_CHNK_FK1` | Preserved | Delete rejected while embeddings exist | History remains | No row rewrite |
| `knowledge_ingestion_requests` | `knowledge_ingestion_events` | `ingestion_request_id` | Existing `KN_INGE_KN_INGREQ_FK1` | Preserved | Request delete rejected while events exist | History remains | Scope compatibility fields derive from the source scope |
| `plugin_invocations` | `plugin_audit_events` | `plugin_invocation_id` | Existing `PLG_AUDEVT_PLG_INV_FK1` | Preserved | Invocation delete rejected while audit events exist | Audit history remains | No rewrite |
| `orac_dropbox.drop_processing_profile` | `drop_location` | `processing_profile_id` | Existing `DRP_LOC_PROFILE_FK` | Preserved | Profile delete rejected while locations exist | Configuration remains | No rewrite |
| Core project/plugin scope | `orac_dropbox.drop_location` and `drop_job` scope snapshots | Cross-schema type/key string | No cross-schema FK; formerly accepted by convention | Supported writes call `orac_plugin.knowledge_scope_validation_api`; eligible LOV; immutable Core keys and permanent Core guards | Core parent delete is always blocked; direct privileged plugin-owner SQL remains outside declarative protection | Location/job history remains; unsupported or inactive scope is unavailable | Existing locations scanned; invalid or stale count must be zero |
| `orac_dropbox.drop_location` | `drop_job` | `drop_location_id` | Existing `DRP_JOB_LOCATION_FK` | Preserved; job retains effective scope snapshot | Location delete rejected while jobs exist | Jobs and snapshots remain | No rewrite |
| `orac_dropbox.drop_job` | `drop_job_event` | `drop_job_id` | Existing `DRP_JOBE_JOB_FK` | Preserved | Job delete rejected while events exist | Event history remains | No rewrite |

## Security and audit

The runtime schema can execute only
`orac_code.rag_usage_authorization_api`. APEX can execute the administrative
package and read reporting/LOV views, but receives no direct Core table access.
Decisions persist or log only principal, canonical scope, route, safe reason
code, bypass flag, counts, and approved timing. Chunk text, embeddings, prompts,
evidence blocks, and complete documents are prohibited.

`allow_all_scopes` defaults to `false` and skips only the matching privilege-row
requirement. It does not bypass authentication, active principal registration,
canonical resolution, registry activity, plugin eligibility, retrieval bounds,
or database failures.

## Architectural exception

Drop Box cannot hold an `ORAC_DROPBOX -> ORAC_CORE` foreign key without
violating the plugin boundary. Supported-path API validation is therefore not a
foreign-key-equivalent guarantee. Direct privileged SQL in the plugin owner can
still insert an invalid string reference; such DML is unsupported and must be
detected by operational integrity scans.
