--==============================================================================
-- orac schema ddl (identity pks, lowercase, separate pk constraints)
--==============================================================================

--------------------------------------------------------------------------------
-- orac.users
--------------------------------------------------------------------------------
create table orac.users (
  user_id      number generated always as identity not null,
  username     varchar2(100) not null,
  display_name varchar2(200),
  email        varchar2(320),
  is_active    char(1) default 'y' not null
                 check (is_active in ('y','n')),
  created_on   timestamp(6) default on null systimestamp not null,
  created_by   varchar2(128) default on null coalesce(
                  sys_context('apex$session','app_user'),
                  sys_context('userenv','proxy_user'),
                  sys_context('userenv','session_user'),
                  user
                ) not null,
  updated_on   timestamp(6),
  updated_by   varchar2(128),
  row_version  number default 1 not null
);

create unique index orac.users_pk on orac.users(user_id);
alter table orac.users
  add constraint users_pk primary key (user_id)
  using index orac.users_pk;

create unique index orac.uq_users_username on orac.users(username);
alter table orac.users
  add constraint uq_users_username unique (username)
  using index orac.uq_users_username;

create or replace trigger orac.users_bu
before update on orac.users
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.conversations
--------------------------------------------------------------------------------
create table orac.conversations (
  conversation_id number generated always as identity not null,
  user_id         number not null,
  session_id      varchar2(64) not null,
  llm_id          number,
  title           varchar2(200),
  state           varchar2(20) default 'open' not null
                   check (state in ('open','closed','archived')),
  created_on      timestamp default on null systimestamp not null,
  created_by      varchar2(128) default on null coalesce(
                     sys_context('apex$session','app_user'),
                     sys_context('userenv','proxy_user'),
                     sys_context('userenv','session_user'),
                     user
                   ) not null,
  updated_on      timestamp,
  updated_by      varchar2(128),
  row_version     number default 1 not null
);

create unique index orac.conversations_pk on orac.conversations(conversation_id);
alter table orac.conversations
  add constraint conversations_pk primary key (conversation_id)
  using index orac.conversations_pk;

create unique index orac.uq_conversations_session on orac.conversations(session_id);
alter table orac.conversations
  add constraint uq_conversations_session unique (session_id)
  using index orac.uq_conversations_session;

create index orac.ix_conversations_user_id on orac.conversations(user_id);
create index orac.ix_conversations_llm_id  on orac.conversations(llm_id);

create or replace trigger orac.conversations_bu
before update on orac.conversations
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.messages
--------------------------------------------------------------------------------
create table orac.messages (
  message_id      number generated always as identity not null,
  conversation_id number not null,
  turn_index      number not null,
  role            varchar2(20) not null
                   check (role in ('system','user','assistant','tool')),
  content         json not null,
  tokens_used     number,
  meta            json,
  llm_id          number,
  created_on      timestamp default on null systimestamp not null,
  created_by      varchar2(128) default on null coalesce(
                     sys_context('apex$session','app_user'),
                     sys_context('userenv','proxy_user'),
                     sys_context('userenv','session_user'),
                     user
                   ) not null,
  updated_on      timestamp,
  updated_by      varchar2(128),
  row_version     number default 1 not null
);

create unique index orac.messages_pk on orac.messages(message_id);
alter table orac.messages
  add constraint messages_pk primary key (message_id)
  using index orac.messages_pk;

create unique index orac.uq_messages_conv_turn on orac.messages(conversation_id, turn_index);
alter table orac.messages
  add constraint uq_messages_conv_turn unique (conversation_id, turn_index)
  using index orac.uq_messages_conv_turn;

create index orac.ix_messages_conv_id on orac.messages(conversation_id);
create index orac.ix_messages_llm_id  on orac.messages(llm_id);

create or replace trigger orac.messages_bu
before update on orac.messages
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.message_embeddings
--------------------------------------------------------------------------------
create table orac.message_embeddings (
  emb_id            number generated always as identity not null,
  message_id        number not null,
  chunk_index       number default 1 not null,
  span_start        number,
  span_end          number,
  lossless_text     clob not null,
  content_snapshot  json,
  embedding         vector(1536) not null,
  embedding_model   varchar2(100) not null,
  embedding_provider varchar2(100) default on null 'oracle' not null,
  distance_metric   varchar2(16) default 'COSINE' not null
                    check (distance_metric in ('COSINE','L2','L2_SQUARED','DOT','MANHATTAN','HAMMING','JACCARD')),
  tokens_used       number,
  created_on        timestamp default on null systimestamp not null,
  created_by        varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on        timestamp,
  updated_by        varchar2(128),
  row_version       number default 1 not null
) lob (lossless_text) store as securefile (enable storage in row)
  lob (content_snapshot) store as securefile (enable storage in row);

create unique index orac.message_embeddings_pk on orac.message_embeddings(emb_id);
alter table orac.message_embeddings
  add constraint message_embeddings_pk primary key (emb_id)
  using index orac.message_embeddings_pk;

create unique index orac.uq_msg_emb_message_chunk on orac.message_embeddings(message_id, chunk_index);
alter table orac.message_embeddings
  add constraint uq_msg_emb_message_chunk unique (message_id, chunk_index)
  using index orac.uq_msg_emb_message_chunk;

create index orac.ix_msg_emb_message_id on orac.message_embeddings(message_id);

create or replace trigger orac.message_embeddings_bu
before update on orac.message_embeddings
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := sys_context('userenv','session_user');
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.llm_registry
--------------------------------------------------------------------------------
create table orac.llm_registry (
  llm_id             number generated always as identity not null,
  name               varchar2(100) not null,
  provider           varchar2(100),
  model              varchar2(200) not null,
  context_policy     varchar2(20) not null
                      check (context_policy in ('model','app','hybrid','external')),
  max_context_tokens number,
  is_enabled         char(1) default 'y' not null
                      check (is_enabled in ('y','n')),
  properties         json,
  created_on         timestamp(6) default on null systimestamp not null,
  created_by         varchar2(128) default on null coalesce(
                        sys_context('apex$session','app_user'),
                        sys_context('userenv','proxy_user'),
                        sys_context('userenv','session_user'),
                        user
                      ) not null,
  updated_on         timestamp(6),
  updated_by         varchar2(128),
  row_version        number default 1 not null
);

create unique index orac.llm_registry_pk on orac.llm_registry(llm_id);
alter table orac.llm_registry
  add constraint llm_registry_pk primary key (llm_id)
  using index orac.llm_registry_pk;

create unique index orac.uq_llm_registry_name on orac.llm_registry(name);
alter table orac.llm_registry
  add constraint uq_llm_registry_name unique (name)
  using index orac.uq_llm_registry_name;

create or replace trigger orac.llm_registry_bu
before update on orac.llm_registry
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.user_preferences
--------------------------------------------------------------------------------
create table orac.user_preferences (
  pref_id     number generated always as identity not null,
  user_id     number not null,
  pref_key    varchar2(100 byte) not null,
  pref_value  json,
  value_type  varchar2(8 byte) default 'string' not null,
  created_on  timestamp default on null systimestamp not null,
  created_by  varchar2(128 byte) default on null coalesce(
                sys_context('apex$session','app_user'),
                sys_context('userenv','proxy_user'),
                sys_context('userenv','session_user'),
                user
              ) not null,
  updated_on  timestamp,
  updated_by  varchar2(128 byte),
  row_version number default 1 not null,
  check (value_type in ('boolean','json','number','string'))
)
  logging
  no inmemory
;

create unique index orac.user_preferences_pk on orac.user_preferences(pref_id);
alter table orac.user_preferences
  add constraint user_preferences_pk primary key (pref_id)
  using index orac.user_preferences_pk;

create unique index orac.uq_user_preferences_user_key on orac.user_preferences(user_id, pref_key);
alter table orac.user_preferences
  add constraint uq_user_preferences_user_key unique (user_id, pref_key)
  using index orac.uq_user_preferences_user_key;

create index orac.ix_user_prefs_uid on orac.user_preferences(user_id);

alter table orac.user_preferences
  add constraint user_pref_ck1
  check (
    ( value_type = 'string'
      and json_value(pref_value, '$' returning varchar2(4000) null on error) is not null
    )
    or
    ( value_type = 'number'
      and json_value(pref_value, '$' returning number null on error) is not null
    )
    or
    ( value_type = 'boolean'
      and lower(json_value(pref_value, '$' returning varchar2(5) null on error)) in ('true','false')
    )
    or
    ( value_type = 'json'
      and json_exists(pref_value, '$')
    )
  );

create or replace trigger orac.trg_user_prefs_bu
before update on orac.user_preferences
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.user_prompt_elements
--------------------------------------------------------------------------------
create table orac.user_prompt_elements (
  element_id     number generated always as identity not null,
  user_id        number not null,
  category_code  varchar2(50) not null,
  prompt_element clob not null,
  weight_score   number(5,2) default 1 not null,
  is_enabled     char(1) default 'y' not null check (is_enabled in ('y','n')),
  created_on     timestamp(6) default on null systimestamp not null,
  created_by     varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on     timestamp(6),
  updated_by     varchar2(128),
  row_version    number default 1 not null
) lob (prompt_element) store as securefile (enable storage in row);

create unique index orac.user_prompt_elements_pk on orac.user_prompt_elements(element_id);
alter table orac.user_prompt_elements
  add constraint user_prompt_elements_pk primary key (element_id)
  using index orac.user_prompt_elements_pk;

create index orac.upe_user_cat_idx on orac.user_prompt_elements(user_id, category_code);

create or replace trigger orac.upe_bu
before update on orac.user_prompt_elements
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.user_synonyms
--------------------------------------------------------------------------------
create table orac.user_synonyms (
  user_id     number not null,
  alias_type  varchar2(16) not null,
  alias_value varchar2(256) not null,
  is_active   char(1) default 'y' not null
               check (is_active in ('y','n')),
  created_on  timestamp(6) default on null systimestamp not null,
  created_by  varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on  timestamp(6),
  updated_by  varchar2(128),
  row_version number default 1 not null
);

create unique index orac.user_synonyms_pk on orac.user_synonyms(alias_type, alias_value);
alter table orac.user_synonyms
  add constraint user_synonyms_pk primary key (alias_type, alias_value)
  using index orac.user_synonyms_pk;

alter table orac.user_synonyms
  add check (alias_type in ('apple','email','google','microsoft','oauth','os','short'));

create index orac.user_synonyms_uid_idx on orac.user_synonyms(user_id);

create or replace trigger orac.user_syns_bu
before update on orac.user_synonyms
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- orac.devices
--------------------------------------------------------------------------------
create table orac.devices (
  device_id   varchar2(128) not null,
  user_id     number not null,
  host_name   varchar2(255),
  is_active   char(1) default 'y' not null
               check (is_active in ('y','n')),
  created_on  timestamp(6) default on null systimestamp not null,
  created_by  varchar2(128) default on null sys_context('userenv','session_user') not null,
  updated_on  timestamp(6),
  updated_by  varchar2(128),
  row_version number default 1 not null
);

create unique index orac.devices_pk on orac.devices(device_id);
alter table orac.devices
  add constraint devices_pk primary key (device_id)
  using index orac.devices_pk;

create index orac.devices_uid_idx on orac.devices(user_id);

create or replace trigger orac.devices_bu
before update on orac.devices
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session','app_user'),
                       sys_context('userenv','proxy_user'),
                       sys_context('userenv','session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

--------------------------------------------------------------------------------
-- foreign keys
--------------------------------------------------------------------------------
alter table orac.conversations
  add constraint fk_conversations_user foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

alter table orac.conversations
  add constraint fk_conversations_llm foreign key (llm_id)
  references orac.llm_registry (llm_id);

alter table orac.messages
  add constraint fk_messages_conversation foreign key (conversation_id)
  references orac.conversations (conversation_id)
  on delete cascade;

alter table orac.messages
  add constraint fk_messages_llm foreign key (llm_id)
  references orac.llm_registry (llm_id);

alter table orac.message_embeddings
  add constraint fk_msg_emb_message foreign key (message_id)
  references orac.messages (message_id)
  on delete cascade;

alter table orac.user_preferences
  add constraint fk_user_preferences_user foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

alter table orac.user_prompt_elements
  add constraint fk_upe_user foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

alter table orac.user_synonyms
  add constraint fk_user_synonyms_user foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

alter table orac.devices
  add constraint fk_devices_user foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

--------------------------------------------------------------------------------
-- views (dashboard)
--------------------------------------------------------------------------------
create or replace view orac_code.messages_per_day_v as
select
  trunc(m.created_on) as day,
  count(*) as messages
from orac_api.messages_v m
group by trunc(m.created_on)
order by day;

create or replace view orac_code.llm_usage_breakdown_v as
select
  l.name as model_name,
  count(*) as usage_count
from orac_api.messages_v m
join orac_api.conversations_v c on m.conversation_id = c.conversation_id
join orac_api.llm_registry_v l on c.llm_id = l.llm_id
group by l.name
order by usage_count desc;

create or replace view orac_code.token_usage_trend_v as
select
  trunc(m.created_on) as day,
  sum(m.tokens_used) as total_tokens
from orac_api.messages_v m
where m.tokens_used is not null
group by trunc(m.created_on)
order by day;

create or replace view orac_code.message_role_breakdown_v as
select
  m.role,
  count(*) as message_count
from orac_api.messages_v m
group by m.role;

create or replace view orac_code.user_preferences_display_v as
select
  p.pref_id,                 -- primary key (unique, not null)
  p.user_id,
  p.pref_key,
  p.value_type,              -- 'string' | 'number' | 'boolean'
  p.row_version,             -- for optimistic locking in APEX (optional but nice)
  /* Human-friendly value with quotes removed for strings */
  case p.value_type
    when 'string'  then json_value(p.pref_value, '$' returning varchar2(4000) null on error)
    when 'number'  then to_char(json_value(p.pref_value, '$' returning number         null on error))
    when 'boolean' then lower(json_value(p.pref_value, '$' returning varchar2(5)     null on error))
  end as value_display
from orac_api.user_preferences_v p;
