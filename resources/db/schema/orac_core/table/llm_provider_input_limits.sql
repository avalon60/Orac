--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines dimension-qualified provider transport bounds.

--changeset clive:create_table_orac_core_llm_provider_input_limits context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_PROVIDER_INPUT_LIMITS';
create table orac_core.llm_provider_input_limits
(
  provider_input_limit_id       number generated always as identity not null,
  provider_input_id             number not null,
  limit_dimension_domain_code   varchar2(100 char) default on null 'LIMIT_DIMENSION' not null,
  limit_dimension_ref_value_code varchar2(100 char) not null,
  bound_operator_domain_code    varchar2(100 char) default on null 'BOUND_OPERATOR' not null,
  bound_operator_ref_value_code varchar2(100 char) not null,
  limit_value                   number not null,
  limit_unit_domain_code        varchar2(100 char) default on null 'LIMIT_UNIT' not null,
  limit_unit_ref_value_code     varchar2(100 char) not null,
  effective_from                timestamp with local time zone default on null systimestamp not null,
  effective_to                  timestamp with local time zone,
  provenance                    varchar2(1000 char) not null,
  created_by                    varchar2(128 char) default on null coalesce(
                                  sys_context('apex$session', 'app_user'),
                                  sys_context('userenv', 'proxy_user'),
                                  sys_context('userenv', 'session_user'),
                                  user
                                ) not null,
  created_on                    timestamp with local time zone default on null systimestamp not null,
  updated_by                    varchar2(128 char),
  updated_on                    timestamp with local time zone,
  row_version                   number default 1 not null
);
--rollback drop table orac_core.llm_provider_input_limits purge;
