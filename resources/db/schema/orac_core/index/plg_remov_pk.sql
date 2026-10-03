--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Indexes plugin_removals.

--changeset clive:create_index_plg_remov_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_REMOV_PK';
create unique index orac_core.plg_remov_pk on orac_core.plugin_removals (removal_id);
--rollback drop index orac_core.plg_remov_pk;
