--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_table context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tables where owner='ORAC_CHESS' and table_name='CHESS_CONTENT_SOURCE'
create table orac_chess.chess_content_source (
  creator varchar2(300 char) not null,
  author varchar2(300 char),
  notes clob,
  created_on timestamp with time zone default systimestamp not null,
  updated_on timestamp with time zone default systimestamp not null,
  row_version number default 1 not null
);
--rollback drop table orac_chess.chess_content_source;
