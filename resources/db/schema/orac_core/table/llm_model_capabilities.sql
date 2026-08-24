--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines reviewed behavioural evidence for exact registered models.

--changeset clive:create_table_orac_core_llm_model_capabilities context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_MODEL_CAPABILITIES';
create table orac_core.llm_model_capabilities
(
  model_capability_id             number generated always as identity not null,
  llm_id                          number not null,
  provider_code                   varchar2(100 char) not null,
  model_identity                  varchar2(200 char) not null,
  capability_code                 varchar2(100 char) not null,
  evidence_state_domain_code      varchar2(100 char) default on null 'CAPABILITY_EVIDENCE_STATE' not null,
  evidence_state_ref_value_code   varchar2(100 char) not null,
  model_revision                  varchar2(255 char) not null,
  source_reference                varchar2(1000 char) not null,
  checked_on                      timestamp with local time zone not null,
  effective_from                  timestamp with local time zone default on null systimestamp not null,
  effective_to                    timestamp with local time zone,
  reviewed_by                     varchar2(128 char) not null,
  provenance                      varchar2(1000 char) not null,
  fixture_identity                varchar2(255 char),
  probe_identity                  varchar2(255 char),
  acceptance_criteria_ref         varchar2(1000 char),
  rejection_reason                varchar2(1000 char),
  native_properties               json,
  created_by                      varchar2(128 char) default on null coalesce(
                                    sys_context('apex$session', 'app_user'),
                                    sys_context('userenv', 'proxy_user'),
                                    sys_context('userenv', 'session_user'),
                                    user
                                  ) not null,
  created_on                      timestamp with local time zone default on null systimestamp not null,
  updated_by                      varchar2(128 char),
  updated_on                      timestamp with local time zone,
  row_version                     number default 1 not null
);
--rollback drop table orac_core.llm_model_capabilities purge;
