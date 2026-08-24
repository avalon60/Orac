--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines provider transport declarations separately from model evidence.

--changeset clive:create_table_orac_core_llm_provider_inputs context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_PROVIDER_INPUTS';
create table orac_core.llm_provider_inputs
(
  provider_input_id                  number generated always as identity not null,
  provider_code                      varchar2(100 char) not null,
  representation_code                varchar2(100 char) not null,
  media_type                         varchar2(255 char),
  evidence_state_domain_code         varchar2(100 char) default on null 'CAPABILITY_EVIDENCE_STATE' not null,
  evidence_state_ref_value_code      varchar2(100 char) not null,
  adapter_status_domain_code         varchar2(100 char) default on null 'ADAPTER_SUPPORT_STATUS' not null,
  adapter_status_ref_value_code      varchar2(100 char) not null,
  source_uri                         varchar2(1000 char) not null,
  checked_on                         timestamp with local time zone not null,
  effective_from                     timestamp with local time zone default on null systimestamp not null,
  effective_to                       timestamp with local time zone,
  reviewed_by                        varchar2(128 char) not null,
  provenance                         varchar2(1000 char) not null,
  rejection_reason                   varchar2(1000 char),
  native_properties                  json,
  created_by                         varchar2(128 char) default on null coalesce(
                                       sys_context('apex$session', 'app_user'),
                                       sys_context('userenv', 'proxy_user'),
                                       sys_context('userenv', 'session_user'),
                                       user
                                     ) not null,
  created_on                         timestamp with local time zone default on null systimestamp not null,
  updated_by                         varchar2(128 char),
  updated_on                         timestamp with local time zone,
  row_version                        number default 1 not null
);
--rollback drop table orac_core.llm_provider_inputs purge;
