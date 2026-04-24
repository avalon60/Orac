alter table orac.orac_personalities
  add constraint orac_personalities_uk1
  unique (personality_code);
