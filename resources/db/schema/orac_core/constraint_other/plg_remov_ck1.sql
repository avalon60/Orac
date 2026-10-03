--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plg_remov_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_REMOV_CK1';
alter table orac_core.plugin_removals add constraint plg_remov_ck1 check (schema_disposition in ('DROP', 'KEEP'));
--rollback alter table orac_core.plugin_removals drop constraint plg_remov_ck1;
