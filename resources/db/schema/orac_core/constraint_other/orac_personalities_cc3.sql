alter table orac.orac_personalities
  add constraint orac_personalities_cc3
  check (verbosity_level in (0,1,2));
