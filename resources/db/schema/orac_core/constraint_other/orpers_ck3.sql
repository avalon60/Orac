alter table orac_core.orac_personalities
  add constraint orpers_ck3
  check (verbosity_level in (0,1,2));
