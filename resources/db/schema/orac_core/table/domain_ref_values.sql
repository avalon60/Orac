--liquibase formatted sql

--changeset clive:create_table_orac_core_domain_ref_values context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'DOMAIN_REF_VALUES';
-- __author__: clive
-- __date__: 2026-08-02
-- __description__: reference values belonging to core-owned reference-data domains

create table orac_core.domain_ref_values
(
  domain_code          varchar2(100 char) not null,
  ref_value_code       varchar2(100 char) not null,
  parent_domain_code   varchar2(100 char),
  parent_ref_value_code varchar2(100 char),
  display_value        varchar2(255 char) not null,
  description          varchar2(4000 char),
  display_sequence     number default 1000 not null,
  icon                 varchar2(255 char),
  color                varchar2(255 char),
  active_yn            varchar2(1 char) default 'Y' not null,
  system_required_yn   varchar2(1 char) default 'N' not null,
  created_by           varchar2(128 char) default on null coalesce(
                         sys_context('apex$session', 'app_user'),
                         sys_context('userenv', 'proxy_user'),
                         sys_context('userenv', 'session_user'),
                         user
                       ) not null,
  created_on           timestamp with local time zone default on null systimestamp not null,
  updated_by           varchar2(128 char),
  updated_on           timestamp with local time zone,
  row_version          number default 1 not null
);

--rollback drop table orac_core.domain_ref_values purge;
