--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_message_embeddings context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy message embeddings access

create or replace synonym orac.message_embeddings for orac_api.message_embeddings_v;

--rollback drop synonym orac.message_embeddings;
