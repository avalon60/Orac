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
create unique index orac_core.orpers_pk
  on orac_core.orac_personalities (personality_id);

create unique index orac_core.orpers_uk1
  on orac_core.orac_personalities (personality_code);

alter table orac_core.orac_personalities
  add constraint orac_personalities_pk
  primary key (personality_id);

alter table orac_core.orac_personalities
  add constraint orac_personalities_uk1
  unique (personality_code);

alter table orac_core.orac_personalities
  add constraint orac_personalities_ck1
  check (attitude_base_level in (0,1,2));

alter table orac_core.orac_personalities
  add constraint orac_personalities_ck2
  check (sarcasm_level in (0,1,2));

alter table orac_core.orac_personalities
  add constraint orac_personalities_ck3
  check (verbosity_level in (0,1,2));


comment on table orac_core.orac_personalities is
  'Defines configurable AI personas for Orac, including behavioural controls, personality flags, and prompt templates used to influence response generation.';

comment on column orac_core.orac_personalities.personality_id is
  'Surrogate primary key for the personality.';

comment on column orac_core.orac_personalities.personality_code is
  'Unique short code identifying the personality (e.g. ORAC_BASE, FRIENDLY).';

comment on column orac_core.orac_personalities.personality_name is
  'Display name of the personality.';

comment on column orac_core.orac_personalities.description is
  'Optional description of the personality''s intended behaviour and characteristics.';

comment on column orac_core.orac_personalities.attitude_base_level is
  'Base attitude level: 0=neutral, 1=dry, 2=begrudging. Used as the default tone before contextual modulation.';

comment on column orac_core.orac_personalities.sarcasm_level is
  'Controls degree of sarcasm or dryness in responses (0=none, 2=strong).';

comment on column orac_core.orac_personalities.verbosity_level is
  'Controls response verbosity: 0=concise, 1=balanced, 2=verbose.';

comment on column orac_core.orac_personalities.allow_humour is
  'Indicates whether light humour may be used in responses.';

comment on column orac_core.orac_personalities.allow_critique is
  'Indicates whether the assistant may challenge or critique user input.';

comment on column orac_core.orac_personalities.enforce_precision is
  'Indicates whether responses should favour precision and correctness over conversational tone.';

comment on column orac_core.orac_personalities.admit_uncertainty is
  'Indicates whether the assistant should explicitly admit uncertainty when unsure.';

comment on column orac_core.orac_personalities.packaged_persona is
  'Flag indicating a system-supplied persona. Packaged personas are immutable and cannot be updated or deleted.';

comment on column orac_core.orac_personalities.system_prompt is
  'Core instruction template defining behavioural rules, constraints, and identity of the assistant.';

comment on column orac_core.orac_personalities.style_prompt is
  'Instruction template defining tone, phrasing, and personality style applied to responses.';

comment on column orac_core.orac_personalities.is_active is
  'Indicates whether the personality is available for selection.';

comment on column orac_core.orac_personalities.created_on is
  'Timestamp when the record was created.';

comment on column orac_core.orac_personalities.created_by is
  'User or process that created the record.';

comment on column orac_core.orac_personalities.updated_on is
  'Timestamp when the record was last updated.';

comment on column orac_core.orac_personalities.updated_by is
  'User or process that last updated the record.';

comment on column orac_core.orac_personalities.row_version is
  'Row version number used for optimistic locking.';
