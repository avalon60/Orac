--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plg_schown_ck3 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_SCHOWN_CK3';
alter table orac_core.plugin_schema_ownership add constraint plg_schown_ck3 check (database_user_id > 0);
--rollback alter table orac_core.plugin_schema_ownership drop constraint plg_schown_ck3;
