--liquibase formatted sql

--changeset cbostock:home_assistant_ha_source_timestamps_add_ha_areas_ha_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name = 'HA_CREATED_AT'
alter table orac_ha.ha_areas add (ha_created_at timestamp with time zone);
--rollback alter table orac_ha.ha_areas drop column ha_created_at;

--changeset cbostock:home_assistant_ha_source_timestamps_add_ha_areas_ha_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name = 'HA_MODIFIED_AT'
alter table orac_ha.ha_areas add (ha_modified_at timestamp with time zone);
--rollback alter table orac_ha.ha_areas drop column ha_modified_at;

--changeset cbostock:home_assistant_ha_source_timestamps_copy_ha_areas_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name in ('CREATED_AT', 'HA_CREATED_AT')
update orac_ha.ha_areas
   set ha_created_at = coalesce(ha_created_at, created_at)
 where created_at is not null;
--rollback empty

--changeset cbostock:home_assistant_ha_source_timestamps_copy_ha_areas_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name in ('MODIFIED_AT', 'HA_MODIFIED_AT')
update orac_ha.ha_areas
   set ha_modified_at = coalesce(ha_modified_at, modified_at)
 where modified_at is not null;
--rollback empty

--changeset cbostock:home_assistant_ha_source_timestamps_drop_ha_areas_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name = 'CREATED_AT'
alter table orac_ha.ha_areas drop column created_at;
--rollback alter table orac_ha.ha_areas add created_at timestamp with time zone;

--changeset cbostock:home_assistant_ha_source_timestamps_drop_ha_areas_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_AREAS' and column_name = 'MODIFIED_AT'
alter table orac_ha.ha_areas drop column modified_at;
--rollback alter table orac_ha.ha_areas add modified_at timestamp with time zone;

--changeset cbostock:home_assistant_ha_source_timestamps_add_ha_devices_ha_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name = 'HA_CREATED_AT'
alter table orac_ha.ha_devices add (ha_created_at timestamp with time zone);
--rollback alter table orac_ha.ha_devices drop column ha_created_at;

--changeset cbostock:home_assistant_ha_source_timestamps_add_ha_devices_ha_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name = 'HA_MODIFIED_AT'
alter table orac_ha.ha_devices add (ha_modified_at timestamp with time zone);
--rollback alter table orac_ha.ha_devices drop column ha_modified_at;

--changeset cbostock:home_assistant_ha_source_timestamps_copy_ha_devices_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name in ('CREATED_AT', 'HA_CREATED_AT')
update orac_ha.ha_devices
   set ha_created_at = coalesce(ha_created_at, created_at)
 where created_at is not null;
--rollback empty

--changeset cbostock:home_assistant_ha_source_timestamps_copy_ha_devices_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name in ('MODIFIED_AT', 'HA_MODIFIED_AT')
update orac_ha.ha_devices
   set ha_modified_at = coalesce(ha_modified_at, modified_at)
 where modified_at is not null;
--rollback empty

--changeset cbostock:home_assistant_ha_source_timestamps_drop_ha_devices_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name = 'CREATED_AT'
alter table orac_ha.ha_devices drop column created_at;
--rollback alter table orac_ha.ha_devices add created_at timestamp with time zone;

--changeset cbostock:home_assistant_ha_source_timestamps_drop_ha_devices_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_DEVICES' and column_name = 'MODIFIED_AT'
alter table orac_ha.ha_devices drop column modified_at;
--rollback alter table orac_ha.ha_devices add modified_at timestamp with time zone;

--changeset cbostock:home_assistant_ha_source_timestamps_add_ha_entities_ha_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name = 'HA_CREATED_AT'
alter table orac_ha.ha_entities add (ha_created_at timestamp with time zone);
--rollback alter table orac_ha.ha_entities drop column ha_created_at;

--changeset cbostock:home_assistant_ha_source_timestamps_add_ha_entities_ha_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name = 'HA_MODIFIED_AT'
alter table orac_ha.ha_entities add (ha_modified_at timestamp with time zone);
--rollback alter table orac_ha.ha_entities drop column ha_modified_at;

--changeset cbostock:home_assistant_ha_source_timestamps_copy_ha_entities_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name in ('CREATED_AT', 'HA_CREATED_AT')
update orac_ha.ha_entities
   set ha_created_at = coalesce(ha_created_at, created_at)
 where created_at is not null;
--rollback empty

--changeset cbostock:home_assistant_ha_source_timestamps_copy_ha_entities_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name in ('MODIFIED_AT', 'HA_MODIFIED_AT')
update orac_ha.ha_entities
   set ha_modified_at = coalesce(ha_modified_at, modified_at)
 where modified_at is not null;
--rollback empty

--changeset cbostock:home_assistant_ha_source_timestamps_drop_ha_entities_created_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name = 'CREATED_AT'
alter table orac_ha.ha_entities drop column created_at;
--rollback alter table orac_ha.ha_entities add created_at timestamp with time zone;

--changeset cbostock:home_assistant_ha_source_timestamps_drop_ha_entities_modified_at context:plugin,prod labels:plugin,home_assistant stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tab_columns where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES' and column_name = 'MODIFIED_AT'
alter table orac_ha.ha_entities drop column modified_at;
--rollback alter table orac_ha.ha_entities add modified_at timestamp with time zone;
