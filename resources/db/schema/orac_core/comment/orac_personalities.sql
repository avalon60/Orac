comment on table orac.orac_personalities is
  'Defines configurable AI personas for Orac, including behavioural controls, personality flags, and prompt templates used to influence response generation.';

comment on column orac.orac_personalities.personality_id is
  'Surrogate primary key for the personality.';

comment on column orac.orac_personalities.personality_code is
  'Unique short code identifying the personality (e.g. ORAC_BASE, FRIENDLY).';

comment on column orac.orac_personalities.personality_name is
  'Display name of the personality.';

comment on column orac.orac_personalities.description is
  'Optional description of the personality''s intended behaviour and characteristics.';

comment on column orac.orac_personalities.attitude_base_level is
  'Base attitude level: 0=neutral, 1=dry, 2=begrudging. Used as the default tone before contextual modulation.';

comment on column orac.orac_personalities.sarcasm_level is
  'Controls degree of sarcasm or dryness in responses (0=none, 2=strong).';

comment on column orac.orac_personalities.verbosity_level is
  'Controls response verbosity: 0=concise, 1=balanced, 2=verbose.';

comment on column orac.orac_personalities.allow_humour is
  'Indicates whether light humour may be used in responses.';

comment on column orac.orac_personalities.allow_critique is
  'Indicates whether the assistant may challenge or critique user input.';

comment on column orac.orac_personalities.enforce_precision is
  'Indicates whether responses should favour precision and correctness over conversational tone.';

comment on column orac.orac_personalities.admit_uncertainty is
  'Indicates whether the assistant should explicitly admit uncertainty when unsure.';

comment on column orac.orac_personalities.packaged_persona is
  'Flag indicating a system-supplied persona. Packaged personas are immutable and cannot be updated or deleted.';

comment on column orac.orac_personalities.system_prompt is
  'Core instruction template defining behavioural rules, constraints, and identity of the assistant.';

comment on column orac.orac_personalities.style_prompt is
  'Instruction template defining tone, phrasing, and personality style applied to responses.';

comment on column orac.orac_personalities.is_active is
  'Indicates whether the personality is available for selection.';

comment on column orac.orac_personalities.created_on is
  'Timestamp when the record was created.';

comment on column orac.orac_personalities.created_by is
  'User or process that created the record.';

comment on column orac.orac_personalities.updated_on is
  'Timestamp when the record was last updated.';

comment on column orac.orac_personalities.updated_by is
  'User or process that last updated the record.';

comment on column orac.orac_personalities.row_version is
  'Row version number used for optimistic locking.';
