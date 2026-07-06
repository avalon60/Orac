--liquibase formatted sql

--changeset clive:create_view_orac_code_view_plugin_service_status_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: runtime-visible plugin service lifecycle status

create or replace view orac_code.plugin_service_status_v as
select plugin_service_id,
       plugin_id,
       service_code,
       plugin_id || ':' || service_code as service_id,
       service_name,
       entry_point,
       execution_model,
       manifest_policy,
       policy_override,
       coalesce(policy_override, manifest_policy) as effective_policy,
       current_state,
       owner_id,
       lease_token,
       lease_expires_on,
       case
         when lease_token is not null
          and lease_expires_on > cast(systimestamp as timestamp) then 'Y'
         else 'N'
       end as lease_active_yn,
       last_started_on,
       last_heartbeat_on,
       last_tick_on,
       last_error_message,
       created_on,
       updated_on,
       row_version
  from orac_api.plugin_services_v;

--rollback drop view orac_code.plugin_service_status_v;
