--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Identifies plugin_schema_ownership.

--changeset clive:create_constraint_plg_schown_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_SCHOWN_PK';
alter table orac_core.plugin_schema_ownership add constraint plg_schown_pk primary key (schema_ownership_id) using index orac_core.plg_schown_pk;
--rollback alter table orac_core.plugin_schema_ownership drop constraint plg_schown_pk;
