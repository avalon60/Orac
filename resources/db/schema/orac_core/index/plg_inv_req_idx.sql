--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plg_inv_req_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_INV_REQ_IDX';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: request correlation index for plugin_invocations


create index orac_core.plg_inv_req_idx
  on orac_core.plugin_invocations
  (
    request_id asc,
    correlation_id asc,
    turn_id asc
  )
;

--rollback drop index orac_core.plg_inv_req_idx;
