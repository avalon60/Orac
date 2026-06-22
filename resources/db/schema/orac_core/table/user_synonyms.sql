--liquibase formatted sql

--changeset clive:create_table_orac_core_table_user_synonyms context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'USER_SYNONYMS';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create table orac_core.user_synonyms
(
  user_id     number not null,
  alias_type  varchar2(16 byte) not null,
  alias_value varchar2(256 byte) not null,
  is_active   char(1 byte) default 'Y' not null,
  created_on  timestamp default on null systimestamp not null,
  created_by  varchar2(128 byte) default on null sys_context('userenv', 'session_user') not null,
  updated_on  timestamp,
  updated_by  varchar2(128 byte),
  row_version number default 1 not null
)
;

--rollback drop table orac_core.user_synonyms purge;
