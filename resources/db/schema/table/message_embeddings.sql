-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create table orac.message_embeddings (
  emb_id             number generated always as identity not null,
  message_id         number not null,
  chunk_index        number default 1 not null,
  span_start         number,
  span_end           number,
  lossless_text      clob not null,
  content_snapshot   json,
  embedding          vector(1536) not null,
  embedding_model    varchar2(100 char) not null,
  embedding_provider varchar2(100 char) default on null 'oracle' not null,
  distance_metric    varchar2(16 char) default 'COSINE' not null,
  tokens_used        number,
  created_on         timestamp with local time zone default on null systimestamp not null,
  created_by         varchar2(128 char) default on null sys_context('userenv','session_user') not null,
  updated_on         timestamp with local time zone,
  updated_by         varchar2(128 char),
  row_version        number default 1 not null
)
  lob (lossless_text) store as securefile (enable storage in row);
