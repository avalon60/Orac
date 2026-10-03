--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plg_schown_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_SCHOWN_CK2';
alter table orac_core.plugin_schema_ownership add constraint plg_schown_ck2 check (schema_name = upper(schema_name) and regexp_like(schema_name, '^[A-Z][A-Z0-9_]{0,127}$'));
--rollback alter table orac_core.plugin_schema_ownership drop constraint plg_schown_ck2;
