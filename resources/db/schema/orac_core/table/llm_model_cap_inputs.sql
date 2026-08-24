--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Associates positive model evidence with representations and optional MIME.

--changeset clive:create_table_orac_core_llm_model_cap_inputs context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_MODEL_CAP_INPUTS';
create table orac_core.llm_model_cap_inputs
(
  model_cap_input_id number generated always as identity not null,
  model_capability_id number not null,
  representation_code varchar2(100 char) not null,
  media_type          varchar2(255 char),
  effective_from      timestamp with local time zone default on null systimestamp not null,
  effective_to        timestamp with local time zone,
  provenance          varchar2(1000 char) not null,
  created_by          varchar2(128 char) default on null coalesce(
                        sys_context('apex$session', 'app_user'),
                        sys_context('userenv', 'proxy_user'),
                        sys_context('userenv', 'session_user'),
                        user
                      ) not null,
  created_on          timestamp with local time zone default on null systimestamp not null,
  updated_by          varchar2(128 char),
  updated_on          timestamp with local time zone,
  row_version         number default 1 not null
);
--rollback drop table orac_core.llm_model_cap_inputs purge;
