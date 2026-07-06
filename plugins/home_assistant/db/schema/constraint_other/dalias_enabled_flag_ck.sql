--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_dalias_enabled_flag_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'DALIAS_ENABLED_FLAG_CK'
alter table orac_ha.device_aliases
        add constraint dalias_enabled_flag_ck
        check (enabled_flag in ('Y', 'N'));

--rollback alter table orac_ha.device_aliases drop constraint dalias_enabled_flag_ck;
