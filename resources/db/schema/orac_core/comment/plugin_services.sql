--liquibase formatted sql

--changeset clive:comment_orac_core_comment_plugin_services context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.plugin_services is
  'Orac-owned lifecycle policy, status, and lease state for plugin services.'
;

comment on column orac_core.plugin_services.plugin_id is
  'Stable plugin identifier from the plugin registry and manifest.'
;

comment on column orac_core.plugin_services.service_code is
  'Stable service code within the plugin; plugin_id plus service_code is the logical service key.'
;

comment on column orac_core.plugin_services.manifest_policy is
  'Default service start policy declared by the installed plugin manifest.'
;

comment on column orac_core.plugin_services.policy_override is
  'Operator override for service start policy; null means use manifest_policy.'
;

comment on column orac_core.plugin_services.current_state is
  'Current Orac-owned service lifecycle state.'
;

comment on column orac_core.plugin_services.owner_id is
  'Unique owner id for the service manager instance that holds the current lease.'
;

comment on column orac_core.plugin_services.lease_token is
  'Opaque token returned by atomic lease acquisition and required for heartbeat/release.'
;

comment on column orac_core.plugin_services.lease_expires_on is
  'Database timestamp after which the lease may be reclaimed.'
;
