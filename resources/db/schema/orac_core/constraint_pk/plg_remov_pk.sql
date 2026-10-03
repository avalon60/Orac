--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Identifies plugin_removals.

--changeset clive:create_constraint_plg_remov_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_REMOV_PK';
alter table orac_core.plugin_removals add constraint plg_remov_pk primary key (removal_id) using index orac_core.plg_remov_pk;
--rollback alter table orac_core.plugin_removals drop constraint plg_remov_pk;
