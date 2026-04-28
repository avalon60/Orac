alter table orac_core.orac_personalities
  add constraint orpers_ck1
  check (attitude_base_level in (0,1,2));
