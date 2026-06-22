--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plgreg_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLGREG_UK1_IDX';
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: unique plugin identifier index for plugin_registry

create unique index orac_core.plgreg_uk1_idx
  on orac_core.plugin_registry(plugin_id);

--rollback drop index orac_core.plgreg_uk1_idx;
