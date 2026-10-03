--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plg_remov_ck3 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_REMOV_CK3';
alter table orac_core.plugin_removals add constraint plg_remov_ck3 check (completed_on is null or (external_complete_yn = 'Y' and files_complete_yn = 'Y'));
--rollback alter table orac_core.plugin_removals drop constraint plg_remov_ck3;
