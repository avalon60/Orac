alter table orac.orac_personalities
  add constraint orac_personalities_cc1
  check (attitude_base_level in (0,1,2));
