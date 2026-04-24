alter table orac.orac_personalities
  add constraint orac_personalities_cc2
  check (sarcasm_level in (0,1,2));
