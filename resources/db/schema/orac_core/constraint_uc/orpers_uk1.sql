alter table orac_core.orac_personalities
  add constraint orpers_uk1
  unique (personality_code);
