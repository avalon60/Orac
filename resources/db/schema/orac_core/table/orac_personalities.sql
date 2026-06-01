create table orac_core.orac_personalities
(
  personality_id        number generated always as identity,
  personality_code      varchar2(30) not null,
  personality_name      varchar2(100) not null,
  description           varchar2(500),

  -- Behaviour controls
  attitude_base_level   number(1) default 1 not null,   -- 0=neutral,1=dry,2=begrudging
  sarcasm_level         number(1) default 1 not null,   -- 0-2
  verbosity_level       number(1) default 1 not null,   -- 0=concise,1=balanced,2=verbose

  -- Behaviour flags (native boolean)
  allow_humour          boolean default true not null,
  allow_critique        boolean default true not null,
  enforce_precision     boolean default true not null,
  admit_uncertainty     boolean default true not null,

  -- Persona classification
  packaged_persona      boolean default false not null,
  model_preset_id       number,

  -- Core instruction templates
  system_prompt         clob,
  style_prompt          clob,

  -- Metadata
  is_active             boolean default true not null,
  created_on            timestamp default systimestamp not null,
  created_by            varchar2(128),
  updated_on            timestamp,
  updated_by            varchar2(128),
  row_version           number default 1 not null
);
