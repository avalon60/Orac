--liquibase formatted sql

--changeset clive:create_index_orac_core_index_orpers_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'ORPERS_UK1_IDX';
create unique index orac_core.orpers_uk1_idx
  on orac_core.orac_personalities (personality_code);

--rollback drop index orac_core.orpers_uk1_idx;
