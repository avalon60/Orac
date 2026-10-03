--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Indexes plugin_schema_ownership.

--changeset clive:create_index_plg_schown_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_SCHOWN_PK';
create unique index orac_core.plg_schown_pk on orac_core.plugin_schema_ownership (schema_ownership_id);
--rollback drop index orac_core.plg_schown_pk;
