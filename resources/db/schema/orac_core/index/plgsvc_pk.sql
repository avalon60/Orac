--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plgsvc_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLGSVC_PK';
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: primary key index for plugin_services

create unique index orac_core.plgsvc_pk
  on orac_core.plugin_services
  (
    plugin_service_id asc
  );

--rollback drop index orac_core.plgsvc_pk;
