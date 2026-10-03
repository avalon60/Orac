--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plg_schown_fidx1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_SCHOWN_FIDX1';
create unique index orac_core.plg_schown_fidx1 on orac_core.plugin_schema_ownership (case when disposition = 'OWNED' then database_identity end, case when disposition = 'OWNED' then schema_name end);
--rollback drop index orac_core.plg_schown_fidx1;
