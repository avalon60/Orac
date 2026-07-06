--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_dalias_alias_name_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'DALIAS_ALIAS_NAME_CK'
alter table orac_ha.device_aliases
        add constraint dalias_alias_name_ck
        check (
          alias_name = lower(trim(alias_name))
          and length(trim(alias_name)) > 0
        );

--rollback alter table orac_ha.device_aliases drop constraint dalias_alias_name_ck;
