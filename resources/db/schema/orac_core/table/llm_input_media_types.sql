--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines exact MIME values and constrained type wildcards.

--changeset clive:create_table_orac_core_llm_input_media_types context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_INPUT_MEDIA_TYPES';
create table orac_core.llm_input_media_types
(
  media_type                     varchar2(255 char) not null,
  display_name                   varchar2(200 char) not null,
  mime_match_kind_domain_code    varchar2(100 char) default on null 'MIME_MATCH_KIND' not null,
  mime_match_kind_ref_value_code varchar2(100 char) not null,
  description                    varchar2(1000 char) not null,
  created_by                     varchar2(128 char) default on null coalesce(
                                   sys_context('apex$session', 'app_user'),
                                   sys_context('userenv', 'proxy_user'),
                                   sys_context('userenv', 'session_user'),
                                   user
                                 ) not null,
  created_on                     timestamp with local time zone default on null systimestamp not null,
  updated_by                     varchar2(128 char),
  updated_on                     timestamp with local time zone,
  row_version                    number default 1 not null
);
--rollback drop table orac_core.llm_input_media_types purge;
