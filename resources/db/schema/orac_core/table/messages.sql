-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create table orac.messages (
  message_id      number generated always as identity not null,
  conversation_id number not null,
  turn_index      number not null,
  role            varchar2(20 char) not null,
  content         json not null,
  tokens_used     number,
  meta            json,
  llm_id          number,
  created_on      timestamp with local time zone default on null systimestamp not null,
  created_by      varchar2(128 char) default on null coalesce(
                     sys_context('apex$session','app_user'),
                     sys_context('userenv','proxy_user'),
                     sys_context('userenv','session_user'),
                     user
                   ) not null,
  updated_on      timestamp with local time zone,
  updated_by      varchar2(128 char),
  row_version     number default 1 not null
);
