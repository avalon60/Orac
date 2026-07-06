--liquibase formatted sql

--changeset cbostock:home_assistant_audit_add_ha_areas_created_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name = 'CREATED_BY'
alter table orac_ha.ha_areas add (created_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_areas drop column created_by;

--changeset cbostock:home_assistant_audit_add_ha_areas_updated_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name = 'UPDATED_BY'
alter table orac_ha.ha_areas add (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_areas drop column updated_by;

--changeset cbostock:home_assistant_audit_add_ha_devices_created_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name = 'CREATED_BY'
alter table orac_ha.ha_devices add (created_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_devices drop column created_by;

--changeset cbostock:home_assistant_audit_add_ha_devices_updated_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name = 'UPDATED_BY'
alter table orac_ha.ha_devices add (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_devices drop column updated_by;

--changeset cbostock:home_assistant_audit_add_ha_entities_created_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name = 'CREATED_BY'
alter table orac_ha.ha_entities add (created_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_entities drop column created_by;

--changeset cbostock:home_assistant_audit_add_ha_entities_updated_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name = 'UPDATED_BY'
alter table orac_ha.ha_entities add (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_entities drop column updated_by;

--changeset cbostock:home_assistant_audit_add_ha_states_current_created_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_STATES_CURRENT' and column_name = 'CREATED_BY'
alter table orac_ha.ha_states_current add (created_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_states_current drop column created_by;

--changeset cbostock:home_assistant_audit_add_ha_states_current_updated_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_STATES_CURRENT' and column_name = 'UPDATED_BY'
alter table orac_ha.ha_states_current add (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_states_current drop column updated_by;

--changeset cbostock:home_assistant_audit_add_ha_sync_runs_created_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_SYNC_RUNS' and column_name = 'CREATED_BY'
alter table orac_ha.ha_sync_runs add (created_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_sync_runs drop column created_by;

--changeset cbostock:home_assistant_audit_add_ha_sync_runs_updated_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_SYNC_RUNS' and column_name = 'UPDATED_BY'
alter table orac_ha.ha_sync_runs add (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.ha_sync_runs drop column updated_by;

--changeset cbostock:home_assistant_audit_add_device_aliases_created_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'DEVICE_ALIASES' and column_name = 'CREATED_BY'
alter table orac_ha.device_aliases add (created_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.device_aliases drop column created_by;

--changeset cbostock:home_assistant_audit_add_device_aliases_updated_by context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'DEVICE_ALIASES' and column_name = 'UPDATED_BY'
alter table orac_ha.device_aliases add (updated_by varchar2(128 char) default coalesce(sys_context('apex$session', 'app_user'), sys_context('userenv', 'proxy_user'), sys_context('userenv', 'session_user'), user) not null);
--rollback alter table orac_ha.device_aliases drop column updated_by;
