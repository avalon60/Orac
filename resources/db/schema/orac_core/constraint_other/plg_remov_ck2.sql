--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plg_remov_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_REMOV_CK2';
alter table orac_core.plugin_removals add constraint plg_remov_ck2 check (external_complete_yn in ('Y', 'N') and files_complete_yn in ('Y', 'N'));
--rollback alter table orac_core.plugin_removals drop constraint plg_remov_ck2;
