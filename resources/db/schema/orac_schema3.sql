--==============================================================================
-- orac schema ddl (compliant with naming standards from DMD design rules)
-- Organized by Object Type
--==============================================================================

--------------------------------------------------------------------------------
-- TABLES
--------------------------------------------------------------------------------

-- table: orac.users — registered users with audit columns and soft-active flag
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

-- table: orac.conversations — dialog threads; optional default LLM per thread
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

-- table: orac.messages — atomic utterances inside a conversation (user/assistant/system/tool)
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

-- table: orac.message_embeddings — per-message chunk embeddings + snapshot
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

-- table: orac.llm_registry — catalog of available LLMs and config/meta
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

-- table: orac.user_preferences — user-level settings (typed JSON scalar + type)
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
  check (value_type in ('boolean','number','string'))
)
  logging
  no inmemory
;

-- table: orac.user_prompt_elements — optional per-user “prompt preface” elements
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

-- table: orac.user_synonyms — alternate identifiers per user (os/email/…)
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

-- table: orac.devices — device registrations tied to a user
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

--------------------------------------------------------------------------------
-- INDEXES
--------------------------------------------------------------------------------

-- pk index: orac.users(user_id)
create unique index orac.users_pk_idx on orac.users(user_id);

-- pk index: orac.conversations(conversation_id)
create unique index orac.convs_pk_idx on orac.conversations(conversation_id);

-- pk index: orac.messages(message_id)
create unique index orac.messgs_pk_idx on orac.messages(message_id);

-- pk index: orac.message_embeddings(emb_id)
create unique index orac.megemb_pk_idx on orac.message_embeddings(emb_id);

-- pk index: orac.llm_registry(llm_id)
create unique index orac.llmreg_pk_idx on orac.llm_registry(llm_id);

-- pk index: orac.user_preferences(pref_id)
create unique index orac.usrprf_pk_idx on orac.user_preferences(pref_id);

-- pk index: orac.user_prompt_elements(element_id)
create unique index orac.usrpre_pk_idx on orac.user_prompt_elements(element_id);

-- pk index: orac.user_synonyms(alias_type, alias_value)
create unique index orac.usrsyns_pk_idx on orac.user_synonyms(alias_type, alias_value);

-- pk index: orac.devices(device_id)
create unique index orac.devics_pk_idx on orac.devices(device_id);

-- uk index: orac.users(username)
create unique index orac.users_uk1_idx on orac.users(username);

-- uk index: orac.conversations(session_id)
create unique index orac.convs_uk1_idx on orac.conversations(session_id);

-- uk index: orac.messages(conversation_id, turn_index)
create unique index orac.messgs_uk1_idx on orac.messages(conversation_id, turn_index);

-- uk index: orac.message_embeddings(message_id, chunk_index)
create unique index orac.megemb_uk1_idx on orac.message_embeddings(message_id, chunk_index);

-- uk index: orac.llm_registry(name)
create unique index orac.llmreg_uk1_idx on orac.llm_registry(name);

-- uk index: orac.user_preferences(user_id, pref_key)
create unique index orac.usrprf_uk1_idx on orac.user_preferences(user_id, pref_key);

-- idx: conversations by user
create index orac.convs_idx1 on orac.conversations(user_id);

-- idx: conversations by llm
create index orac.convs_idx2 on orac.conversations(llm_id);

-- idx: messages by conversation
create index orac.messgs_idx1 on orac.messages(conversation_id);

-- idx: messages by llm
create index orac.messgs_idx2 on orac.messages(llm_id);

-- idx: message_embeddings by message
create index orac.megemb_idx1 on orac.message_embeddings(message_id);

-- idx: user_preferences by user
create index orac.usrprf_idx1 on orac.user_preferences(user_id);

-- idx: user_prompt_elements by (user, category)
create index orac.usrpre_idx1 on orac.user_prompt_elements(user_id, category_code);

-- idx: user_synonyms by user
create index orac.usrsyns_idx1 on orac.user_synonyms(user_id);

-- idx: devices by user
create index orac.devics_idx1 on orac.devices(user_id);

--------------------------------------------------------------------------------
-- PRIMARY KEY CONSTRAINTS
--------------------------------------------------------------------------------

-- pk: users(user_id)
alter table orac.users
  add constraint users_pk primary key (user_id)
  using index orac.users_pk_idx;

-- pk: conversations(conversation_id)
alter table orac.conversations
  add constraint convs_pk primary key (conversation_id)
  using index orac.convs_pk_idx;

-- pk: messages(message_id)
alter table orac.messages
  add constraint messgs_pk primary key (message_id)
  using index orac.messgs_pk_idx;

-- pk: message_embeddings(emb_id)
alter table orac.message_embeddings
  add constraint megemb_pk primary key (emb_id)
  using index orac.megemb_pk_idx;

-- pk: llm_registry(llm_id)
alter table orac.llm_registry
  add constraint llmreg_pk primary key (llm_id)
  using index orac.llmreg_pk_idx;

-- pk: user_preferences(pref_id)
alter table orac.user_preferences
  add constraint usrprf_pk primary key (pref_id)
  using index orac.usrprf_pk_idx;

-- pk: user_prompt_elements(element_id)
alter table orac.user_prompt_elements
  add constraint usrpre_pk primary key (element_id)
  using index orac.usrpre_pk_idx;

-- pk: user_synonyms(alias_type, alias_value)
alter table orac.user_synonyms
  add constraint usrsyns_pk primary key (alias_type, alias_value)
  using index orac.usrsyns_pk_idx;

-- pk: devices(device_id)
alter table orac.devices
  add constraint devics_pk primary key (device_id)
  using index orac.devics_pk_idx;

--------------------------------------------------------------------------------
-- UNIQUE KEY CONSTRAINTS
--------------------------------------------------------------------------------

-- uk: users(username)
alter table orac.users
  add constraint users_uk1 unique (username)
  using index orac.users_uk1_idx;

-- uk: conversations(session_id)
alter table orac.conversations
  add constraint convs_uk1 unique (session_id)
  using index orac.convs_uk1_idx;

-- uk: messages(conversation_id, turn_index)
alter table orac.messages
  add constraint messgs_uk1 unique (conversation_id, turn_index)
  using index orac.messgs_uk1_idx;

-- uk: message_embeddings(message_id, chunk_index)
alter table orac.message_embeddings
  add constraint megemb_uk1 unique (message_id, chunk_index)
  using index orac.megemb_uk1_idx;

-- uk: llm_registry(name)
alter table orac.llm_registry
  add constraint llmreg_uk1 unique (name)
  using index orac.llmreg_uk1_idx;

-- uk: user_preferences(user_id, pref_key)
alter table orac.user_preferences
  add constraint usrprf_uk1 unique (user_id, pref_key)
  using index orac.usrprf_uk1_idx;

--------------------------------------------------------------------------------
-- CHECK CONSTRAINTS
--------------------------------------------------------------------------------

-- ck: enforce value_type alignment with scalar stored in pref_value
alter table orac.user_preferences
  add constraint usrprf_ck1
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
  );

-- ck: valid alias_type domain
alter table orac.user_synonyms
  add constraint usrsyns_ck1
  check (alias_type in ('apple','email','google','microsoft','oauth','os','short'));

--------------------------------------------------------------------------------
-- FOREIGN KEY CONSTRAINTS
--------------------------------------------------------------------------------

-- fk: conversations.user_id → users.user_id (cascade delete)
alter table orac.conversations
  add constraint convs_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: conversations.llm_id → llm_registry.llm_id
alter table orac.conversations
  add constraint convs_llmreg_fk1 foreign key (llm_id)
  references orac.llm_registry (llm_id);

-- fk: messages.conversation_id → conversations.conversation_id (cascade delete)
alter table orac.messages
  add constraint messgs_convs_fk1 foreign key (conversation_id)
  references orac.conversations (conversation_id)
  on delete cascade;

-- fk: messages.llm_id → llm_registry.llm_id
alter table orac.messages
  add constraint messgs_llmreg_fk1 foreign key (llm_id)
  references orac.llm_registry (llm_id);

-- fk: message_embeddings.message_id → messages.message_id (cascade delete)
alter table orac.message_embeddings
  add constraint megemb_messgs_fk1 foreign key (message_id)
  references orac.messages (message_id)
  on delete cascade;

-- fk: user_preferences.user_id → users.user_id (cascade delete)
alter table orac.user_preferences
  add constraint usrprf_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: user_prompt_elements.user_id → users.user_id (cascade delete)
alter table orac.user_prompt_elements
  add constraint usrpre_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: user_synonyms.user_id → users.user_id (cascade delete)
alter table orac.user_synonyms
  add constraint usrsyns_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: devices.user_id → users.user_id (cascade delete)
alter table orac.devices
  add constraint devics_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

--------------------------------------------------------------------------------
-- TRIGGERS
--------------------------------------------------------------------------------

-- trg: users_bu — standard row_version + audit on update
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

-- trg: conversations_bu — standard row_version + audit on update
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

-- trg: messages_bu — standard row_version + audit on update
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

-- trg: message_embeddings_bu — standard row_version + audit on update
create or replace trigger orac.message_embeddings_bu
before update on orac.message_embeddings
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := sys_context('userenv','session_user');
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/

-- trg: llm_registry_bu — standard row_version + audit on update
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

-- trg: trg_user_prefs_bu — standard row_version + audit on update
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

-- trg: upe_bu — standard row_version + audit on update
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

-- trg: user_syns_bu — standard row_version + audit on update
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

-- trg: devices_bu — standard row_version + audit on update
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
-- VIEWS
--------------------------------------------------------------------------------

-- view: messages_per_day_v — daily message counts (NOTE: ORDER BY in views is ignored at query time)
create or replace view orac.messages_per_day_v as
select
  trunc(m.created_on) as day,
  count(*) as messages
from orac.messages m
group by trunc(m.created_on)
order by day;

-- view: llm_usage_breakdown_v — message counts by conversation default llm
create or replace view orac.llm_usage_breakdown_v as
select
  l.name as model_name,
  count(*) as usage_count
from orac.messages m
join orac.conversations c on m.conversation_id = c.conversation_id
join orac.llm_registry l on c.llm_id = l.llm_id
group by l.name
order by usage_count desc;

-- view: token_usage_trend_v — total tokens per day (where tracked)
create or replace view orac.token_usage_trend_v as
select
  trunc(m.created_on) as day,
  sum(m.tokens_used) as total_tokens
from orac.messages m
where m.tokens_used is not null
group by trunc(m.created_on)
order by day;

-- view: message_role_breakdown_v — counts by role
create or replace view orac.message_role_breakdown_v as
select
  m.role,
  count(*) as message_count
from orac.messages m
group by m.role;

-- view: user_preferences_v — friendly projection with display-ready scalar (no quotes for strings)
create or replace view orac.user_preferences_v as
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
from orac.user_preferences p;

--------------------------------------------------------------------------------
-- VIEW CONSTRAINTS (Pseudo/Metadata)
--------------------------------------------------------------------------------

-- pseudo pk on view: user_preferences_v(pref_id) for APEX metadata only
alter view orac.user_preferences_v
  add constraint user_prefs_v_pk
  primary key (pref_id)
  rely disable novalidate;

-- pseudo uk on view: user_preferences_v(user_id, pref_key) for APEX metadata only
alter view orac.user_preferences_v
  add constraint uq_user_prefs_v_user_key
  unique (user_id, pref_key)
  rely disable novalidate;

--------------------------------------------------------------------------------
-- INSTEAD OF TRIGGERS (for Views)
--------------------------------------------------------------------------------

-- iot: user_preferences_v_iud — normalize display value → JSON scalar; route DML to base table
create or replace trigger orac.user_preferences_v_iud
instead of insert or update or delete on orac.user_preferences_v
for each row
declare
  l_json_txt  clob;        -- JSON text to pass to json(...)
  l_bool_txt  varchar2(5);
  l_new_id    number;
begin
  if inserting or updating then
    if :new.value_type not in ('string','number','boolean') then
      raise_application_error(-20002, 'Unknown value_type: '||:new.value_type);
    end if;

    if :new.value_type = 'string' then
      l_json_txt := '"' || replace(nvl(:new.value_display,''), '"', '\"') || '"';
    elsif :new.value_type = 'number' then
      begin
        declare d number; begin d := to_number(trim(:new.value_display)); end;
      exception when others then
        raise_application_error(-20003, 'Invalid number: '||:new.value_display);
      end;
      l_json_txt := trim(:new.value_display);
    else
      l_bool_txt :=
        case lower(nvl(:new.value_display,'false'))
          when 'true' then 'true'
          when '1'    then 'true'
          when 'yes'  then 'true'
          when 'y'    then 'true'
          else 'false'
        end;
      l_json_txt := l_bool_txt;
    end if;
  end if;

  if inserting then
    insert into orac.user_preferences (user_id, pref_key, value_type, pref_value)
    values (:new.user_id, :new.pref_key, :new.value_type, json(l_json_txt))
    returning pref_id into l_new_id;
    -- NOTE: cannot assign :new.pref_id in INSTEAD OF trigger; allow APEX to re-query

  elsif updating then
    update orac.user_preferences
       set user_id    = :new.user_id,
           pref_key   = :new.pref_key,
           value_type = :new.value_type,
           pref_value = json(l_json_txt)
     where pref_id = :old.pref_id;

  elsif deleting then
    delete from orac.user_preferences
     where pref_id = :old.pref_id;
  end if;
end;
/

