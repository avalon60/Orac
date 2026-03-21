--------------------------------------------------------------------------------
-- CHECK CONSTRAINTS
--------------------------------------------------------------------------------

-- users table check constraints
alter table orac.users
  add constraint users_ck1
  check (is_active in ('y','n'));

-- conversations table check constraints
alter table orac.conversations
  add constraint convs_ck1
  check (state in ('open','closed','archived'));

-- messages table check constraints
alter table orac.messages
  add constraint messgs_ck1
  check (role in ('system','user','assistant','tool'));

-- message_embeddings table check constraints
alter table orac.message_embeddings
  add constraint megemb_ck1
  check (distance_metric in ('COSINE','L2','L2_SQUARED','DOT','MANHATTAN','HAMMING','JACCARD'));

-- llm_registry table check constraints
alter table orac.llm_registry
  add constraint llmreg_ck1
  check (context_policy in ('model','app','hybrid','external'));

alter table orac.llm_registry
  add constraint llmreg_ck2
  check (is_enabled in ('y','n'));
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
-- user_preferences table check constraints
alter table orac.user_preferences
  add constraint usrprf_ck2
  check (value_type in ('boolean','number','string'));

-- user_prompt_elements table check constraints
alter table orac.user_prompt_elements
  add constraint usrpre_ck1
  check (is_enabled in ('y','n'));

-- ck: valid alias_type domain
alter table orac.user_synonyms
  add constraint usrsyns_ck1
  check (alias_type in ('apple','email','google','microsoft','oauth','os','short'));

-- user_synonyms table check constraints
alter table orac.user_synonyms
  add constraint usrsyns_ck2
  check (is_active in ('y','n'));

-- devices table check constraints
alter table orac.devices
  add constraint devics_ck1
  check (is_active in ('y','n'));
