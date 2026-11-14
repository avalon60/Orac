--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Core governed relational query persistence.
-- Purpose: Install the independent relational query contract.
-- Usage: Included through the production schema controller.

--changeset clive:relational_query_orac_core_table_relational_query_catalogue context:core labels:core,relational_query stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_objects where owner='ORAC_CORE' and object_name='RELATIONAL_QUERY_CATALOGUE';
create table orac_core.relational_query_catalogue (
  dataset_id varchar2(128 char) not null,
  plugin_id varchar2(128 char) not null,
  metadata_version varchar2(128 char) not null,
  manifest_hash varchar2(64 char) not null,
  declaration_json clob not null,
  verified_yn varchar2(1 char) default 'N' not null,
  evidence_json clob,
  verified_on timestamp with time zone
) logging no inmemory;
--rollback drop table orac_core.relational_query_catalogue;
