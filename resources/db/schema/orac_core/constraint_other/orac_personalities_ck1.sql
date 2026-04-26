alter table orac.orac_personalities
  add constraint orac_personalities_ck1
  check (attitude_base_level in (0,1,2));
