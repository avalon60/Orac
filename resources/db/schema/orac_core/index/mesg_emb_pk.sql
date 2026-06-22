--liquibase formatted sql

--changeset clive:create_index_orac_core_index_mesg_emb_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'MESG_EMB_PK';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.mesg_emb_pk
  on orac_core.message_embeddings
  (
    emb_id asc
  )
;

--rollback drop index orac_core.mesg_emb_pk;
