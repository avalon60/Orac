--------------------------------------------------------------------------------
-- orac.users
--------------------------------------------------------------------------------
create table orac.users (
  user_id      number generated always as identity primary key,
  username     varchar2(100) not null,
  display_name varchar2(200),
  email        varchar2(320),
  is_active    char(1) default 'Y' not null
                 check (is_active in ('Y','N')),
  created_on   timestamp(6) default systimestamp not null,
  created_by   varchar2(128) default coalesce(
                  sys_context('APEX$SESSION','APP_USER'),
                  sys_context('USERENV','PROXY_USER'),
                  sys_context('USERENV','SESSION_USER'),
                  user
                ) not null,
  updated_on   timestamp(6),
  updated_by   varchar2(128),
  row_version  number default 1 not null
);

alter table orac.users
  add constraint uq_users_username unique (username);

create or replace trigger orac.trg_users_bu
before update on orac.users
for each row
begin
  :new.updated_on  := systimestamp;
  :new.updated_by  := coalesce(
                         sys_context('APEX$SESSION','APP_USER'),
                         sys_context('USERENV','PROXY_USER'),
                         sys_context('USERENV','SESSION_USER'),
                         user
                       );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/
--------------------------------------------------------------------------------
-- orac.user_preferences
--------------------------------------------------------------------------------
create table orac.user_preferences (
  pref_id      number generated always as identity primary key,
  user_id      number not null,
  pref_key     varchar2(100) not null,
  pref_value   json,
  created_on   timestamp(6) default systimestamp not null,
  created_by   varchar2(128) default coalesce(
                  sys_context('APEX$SESSION','APP_USER'),
                  sys_context('USERENV','PROXY_USER'),
                  sys_context('USERENV','SESSION_USER'),
                  user
                ) not null,
  updated_on   timestamp(6),
  updated_by   varchar2(128),
  row_version  number default 1 not null
);

alter table orac.user_preferences
  add constraint uq_user_preferences_user_key unique (user_id, pref_key);

create or replace trigger orac.trg_user_prefs_bu
before update on orac.user_preferences
for each row
begin
  :new.updated_on  := systimestamp;
  :new.updated_by  := coalesce(
                         sys_context('APEX$SESSION','APP_USER'),
                         sys_context('USERENV','PROXY_USER'),
                         sys_context('USERENV','SESSION_USER'),
                         user
                       );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/
--------------------------------------------------------------------------------
-- orac.llm_registry
--------------------------------------------------------------------------------
create table orac.llm_registry (
  llm_id             number generated always as identity primary key,
  name               varchar2(100) not null,
  provider           varchar2(100),
  model              varchar2(200) not null,
  context_policy     varchar2(20) not null
                       check (context_policy in ('model','app','hybrid','external')),
  max_context_tokens number,
  is_enabled         char(1) default 'Y' not null
                       check (is_enabled in ('Y','N')),
  properties         json,
  created_on         timestamp(6) default systimestamp not null,
  created_by         varchar2(128) default coalesce(
                        sys_context('APEX$SESSION','APP_USER'),
                        sys_context('USERENV','PROXY_USER'),
                        sys_context('USERENV','SESSION_USER'),
                        user
                      ) not null,
  updated_on         timestamp(6),
  updated_by         varchar2(128),
  row_version        number default 1 not null
);

alter table orac.llm_registry
  add constraint uq_llm_registry_name unique (name);

create or replace trigger orac.trg_llm_registry_bu
before update on orac.llm_registry
for each row
begin
  :new.updated_on  := systimestamp;
  :new.updated_by  := coalesce(
                         sys_context('APEX$SESSION','APP_USER'),
                         sys_context('USERENV','PROXY_USER'),
                         sys_context('USERENV','SESSION_USER'),
                         user
                       );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/
--------------------------------------------------------------------------------
-- orac.context_history
--------------------------------------------------------------------------------
create table orac.context_history (
  ctx_id      number generated always as identity primary key,
  user_id     number not null,
  llm_id      number,
  session_id  varchar2(64) not null,
  turn_index  number not null,
  role        varchar2(20) not null
                check (role in ('system','user','assistant','tool')),
  content     json not null,
  tokens_used number,
  meta        json,
  created_on  timestamp(6) default systimestamp not null,
  created_by  varchar2(128) default coalesce(
                 sys_context('APEX$SESSION','APP_USER'),
                 sys_context('USERENV','PROXY_USER'),
                 sys_context('USERENV','SESSION_USER'),
                 user
               ) not null,
  updated_on  timestamp(6),
  updated_by  varchar2(128),
  row_version number default 1 not null
);

alter table orac.context_history
  add constraint uq_ctx_hist_session_turn unique (session_id, turn_index);

create or replace trigger orac.trg_ctx_hist_bu
before update on orac.context_history
for each row
begin
  :new.updated_on  := systimestamp;
  :new.updated_by  := coalesce(
                         sys_context('APEX$SESSION','APP_USER'),
                         sys_context('USERENV','PROXY_USER'),
                         sys_context('USERENV','SESSION_USER'),
                         user
                       );
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/
--------------------------------------------------------------------------------
-- orac.context_embeddings
--------------------------------------------------------------------------------
create table orac.context_embeddings (
  emb_id            number generated always as identity primary key,
  ctx_id            number not null,
  chunk_index       number default 1 not null,
  span_start        number,
  span_end          number,
  lossless_text     clob not null,
  content_snapshot  json,
  embedding         vector not null,
  embedding_model   varchar2(100) not null,
  embedding_provider varchar2(100),
  distance_metric   varchar2(16) default 'COSINE' not null
                      check (distance_metric in ('COSINE','L2','L2_SQUARED','DOT','MANHATTAN','HAMMING','JACCARD')),
  tokens_used       number,
  created_on        timestamp(6) default systimestamp not null,
  created_by        varchar2(128) default sys_context('USERENV','SESSION_USER') not null,
  updated_on        timestamp(6),
  updated_by        varchar2(128),
  row_version       number default 1 not null
);

alter table orac.context_embeddings
  add constraint uq_ctx_emb_turn_chunk unique (ctx_id, chunk_index);

create or replace trigger orac.trg_ctx_emb_bu
before update on orac.context_embeddings
for each row
begin
  :new.updated_on  := systimestamp;
  :new.updated_by  := sys_context('USERENV','SESSION_USER');
  :new.row_version := nvl(:old.row_version,1) + 1;
end;
/
--------------------------------------------------------------------------------
-- Foreign keys (constraint names unqualified)
--------------------------------------------------------------------------------
alter table orac.user_preferences
  add constraint fk_user_preferences_user
      foreign key (user_id) references orac.users(user_id)
      on delete cascade;

alter table orac.context_history
  add constraint fk_ctx_hist_user
      foreign key (user_id) references orac.users(user_id)
      on delete cascade;

alter table orac.context_history
  add constraint fk_ctx_hist_llm
      foreign key (llm_id) references orac.llm_registry(llm_id);

alter table orac.context_embeddings
  add constraint fk_ctx_emb_ctx
      foreign key (ctx_id) references orac.context_history(ctx_id)
      on delete cascade;

