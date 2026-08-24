--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines the provider-neutral P2-02 capability catalogue.

--changeset clive:create_table_orac_core_llm_capabilities context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_CAPABILITIES';
create table orac_core.llm_capabilities
(
  capability_code                    varchar2(100 char) not null,
  display_name                       varchar2(200 char) not null,
  capability_class_domain_code       varchar2(100 char) default on null 'CAPABILITY_CLASS' not null,
  capability_class_ref_value_code    varchar2(100 char) not null,
  capability_lifecycle_domain_code   varchar2(100 char) default on null 'CAPABILITY_LIFECYCLE' not null,
  capability_lifecycle_ref_value_code varchar2(100 char) not null,
  behaviour_summary                  varchar2(4000 char) not null,
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
--rollback drop table orac_core.llm_capabilities purge;
