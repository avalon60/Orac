--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_pk_dalias_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'DALIAS_PK'
alter table orac_ha.device_aliases
        add constraint dalias_pk
        primary key (alias_name, entity_id)
        using index orac_ha.dalias_pk_idx;

--rollback alter table orac_ha.device_aliases drop constraint dalias_pk;
