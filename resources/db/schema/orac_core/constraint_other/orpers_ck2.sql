alter table orac_core.orac_personalities
  add constraint orpers_ck2
  check (sarcasm_level in (0,1,2));
