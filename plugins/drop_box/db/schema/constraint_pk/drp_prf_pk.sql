--liquibase formatted sql
declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_DROPBOX'
     and constraint_name = 'DRP_PRF_PK';

  if l_count = 0
  then
    execute immediate
      'alter table orac_dropbox.drop_processing_profile add constraint drp_prf_pk primary key (profile_code) using index orac_dropbox.drp_prf_pk_idx';
  end if;
end;
/
