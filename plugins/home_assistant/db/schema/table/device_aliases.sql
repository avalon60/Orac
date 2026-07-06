--liquibase formatted sql

--changeset cbostock:home_assistant_table_device_aliases context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_HA' and table_name = 'DEVICE_ALIASES'
create table orac_ha.device_aliases
      (
        alias_name   varchar2(255 char) not null,
        entity_id   varchar2(255 char) not null,
        enabled_flag varchar2(1 char) default 'Y' not null,
        created_by   varchar2(128 char) default coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     ) not null,
        created_on   timestamp with time zone default systimestamp not null,
        updated_by   varchar2(128 char) default coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     ) not null,
        updated_on   timestamp with time zone default systimestamp not null,
        row_version  number default 1 not null
      )
      logging
      no inmemory;

--rollback drop table orac_ha.device_aliases;
