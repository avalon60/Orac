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

