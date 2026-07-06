--liquibase formatted sql
declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_DROPBOX'
     and constraint_name = 'DRP_PRF_ACTIVE_CK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_dropbox.drop_processing_profile add constraint drp_prf_active_ck
  check (active_yn in ('Y', 'N'))
    ~';
  end if;

  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_DROPBOX'
     and constraint_name = 'DRP_PRF_SYSTEM_CK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_dropbox.drop_processing_profile add constraint drp_prf_system_ck
  check (system_yn in ('Y', 'N'))
    ~';
  end if;

  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_DROPBOX'
     and constraint_name = 'DRP_PRF_CODE_CK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_dropbox.drop_processing_profile add constraint drp_prf_code_ck
  check (regexp_like(profile_code, '^[a-z][a-z0-9_]{1,99}$'))
    ~';
  end if;
end;
/
