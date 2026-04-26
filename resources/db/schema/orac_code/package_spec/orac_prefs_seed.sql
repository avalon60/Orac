-- __author__: clive
-- __date__: 2026-04-25
-- __description__: seed default user preferences through the ORAC_API surface

create or replace package orac_code.orac_prefs_seed as
  function defaults_q return sys.odcivarchar2list pipelined;

  procedure seed_user(
    p_user_id   in number,
    p_overwrite in boolean default false
  );

  procedure seed_all(
    p_overwrite in boolean default false
  );
end orac_prefs_seed;
/
