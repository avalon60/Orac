alter table orac.orac_personalities
  add constraint orpers_uk1
  unique (personality_code);
