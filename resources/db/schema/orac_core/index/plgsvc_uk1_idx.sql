--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plgsvc_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLGSVC_UK1_IDX';
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: unique plugin service logical key index

create unique index orac_core.plgsvc_uk1_idx
  on orac_core.plugin_services
  (
    plugin_id asc,
    service_code asc
  );

--rollback drop index orac_core.plgsvc_uk1_idx;
