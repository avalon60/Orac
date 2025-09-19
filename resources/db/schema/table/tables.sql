--==============================================================================
-- orac schema ddl (compliant with naming standards from dmd design rules)
-- All audit timestamps are TIMESTAMP WITH LOCAL TIME ZONE
--==============================================================================

--------------------------------------------------------------------------------
-- TABLES
--------------------------------------------------------------------------------

-- table: orac.users
create table orac.users (
  user_id      number generated always as identity not null,
  username     varchar2(100) not null,
  display_name varchar2(200),
  email        varchar2(320),
  is_active    char(1) default 'y' not null,
  created_on   timestamp(6) with local time zone default on null systimestamp not null,
  created_by   varchar2(128) default on null coalesce(
                  sys_context('apex$session','app_user'),
                  sys_context('userenv','proxy_user'),
                  sys_context('userenv','session_user'),
                  user
                ) not null,
  updated_on   timestamp(6) with local time zone,
  updated_by   varchar2(128),
  row_version  number default 1 not null
);

-- table: orac.conversations
create table orac.conversations (
  conversation_id number generated always as identity not null,
  user_id         number not null,
  session_id      varchar2(64) not null,
  llm_id          number,
  title           varchar2(200) default on null 'Brief exchange...',
  state           varchar2(20) default 'open' not null,
  created_on      timestamp with local time zone default on null systimestamp not null,
  created_by      varchar2(128) default on null coalesce(
                     sys_context('apex$session','app_user'),
                     sys_context('userenv','proxy_user'),
                     sys_context('userenv','session_user'),
                     user
                   ) not null,
  updated_on      timestamp with local time zone,
  updated_by      varchar2(128),
  row_version     number default 1 not null
);

-- table: orac.messages
create table orac.messages (
  message_id      number generated always as identity not null,
  conversation_id number not null,
  turn_index      number not null,
  role            varchar2(20) not null,
  content         json not null,
  tokens_used     number,
  meta            json,
  llm_id          number,
  created_on      timestamp with local time zone default on null systimestamp not null,
  created_by      varchar2(128) default on null coalesce(
                     sys_context('apex$session','app_user'),
                     sys_context('userenv','proxy_user'),
                     sys_context('userenv','session_user'),
                     user
                   ) not null,
  updated_on      timestamp with local time zone,
  updated_by      varchar2(128),
  row_version     number default 1 not null
);

-- table: orac.message_embeddings
create table orac.message_embeddings (
  emb_id             number generated always as identity not null,
  message_id         number not null,
  chunk_index        number default 1 not null,
  span_start         number,
  span_end           number,
  lossless_text      clob not null,
  content_snapshot   json,
  embedding          vector(1536) not null,
  embedding_model    varchar2(100) not null,
  embedding_provider varchar2(100) default on null 'oracle' not null,
  distance_metric    varchar2(16) default 'COSINE' not null,
  tokens_used        number,
  created_on         timestamp with local time zone default on null systimestamp not null,
  created_by         varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on         timestamp with local time zone,
  updated_by         varchar2(128),
  row_version        number default 1 not null
)
  lob (lossless_text) store as securefile (enable storage in row);

-- table: orac.llm_registry
create table orac.llm_registry (
  llm_id             number generated always as identity not null,
  name               varchar2(100) not null,
  provider           varchar2(100),
  model              varchar2(200) not null,
  context_policy     varchar2(20) not null,
  max_context_tokens number,
  is_enabled         char(1) default 'y' not null,
  properties         json,
  created_on         timestamp(6) with local time zone default on null systimestamp not null,
  created_by         varchar2(128) default on null coalesce(
                        sys_context('apex$session','app_user'),
                        sys_context('userenv','proxy_user'),
                        sys_context('userenv','session_user'),
                        user
                      ) not null,
  updated_on         timestamp(6) with local time zone,
  updated_by         varchar2(128),
  row_version        number default 1 not null
);

-- table: orac.user_preferences
create table orac.user_preferences (
  pref_id     number generated always as identity not null,
  user_id     number not null,
  pref_key    varchar2(100 byte) not null,
  pref_value  json,
  value_type  varchar2(8 byte) default 'string' not null,
  created_on  timestamp with local time zone default on null systimestamp not null,
  created_by  varchar2(128 byte) default on null coalesce(
                sys_context('apex$session','app_user'),
                sys_context('userenv','proxy_user'),
                sys_context('userenv','session_user'),
                user
              ) not null,
  updated_on  timestamp with local time zone,
  updated_by  varchar2(128 byte),
  row_version number default 1 not null
)
  logging
  no inmemory
;

-- table: orac.user_prompt_elements
create table orac.user_prompt_elements (
  element_id     number generated always as identity not null,
  user_id        number not null,
  category_code  varchar2(50) not null,
  prompt_element clob not null,
  weight_score   number(5,2) default 1 not null,
  is_enabled     char(1) default 'y' not null,
  created_on     timestamp(6) with local time zone default on null systimestamp not null,
  created_by     varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on     timestamp(6) with local time zone,
  updated_by     varchar2(128),
  row_version    number default 1 not null
) lob (prompt_element) store as securefile (enable storage in row);

-- table: orac.user_synonyms
create table orac.user_synonyms (
  user_id     number not null,
  alias_type  varchar2(16) not null,
  alias_value varchar2(256) not null,
  is_active   char(1) default 'y' not null,
  created_on  timestamp(6) with local time zone default on null systimestamp not null,
  created_by  varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on  timestamp(6) with local time zone,
  updated_by  varchar2(128),
  row_version number default 1 not null
);

-- table: orac.devices
create table orac.devices (
  device_id   varchar2(128) not null,
  user_id     number not null,
  host_name   varchar2(255),
  is_active   char(1) default 'y' not null,
  created_on  timestamp(6) with local time zone default on null systimestamp not null,
  created_by  varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on  timestamp(6) with local time zone,
  updated_by  varchar2(128),
  row_version number default 1 not null
);

