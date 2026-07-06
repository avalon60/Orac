--liquibase formatted sql
declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_constraints
   where owner = 'ORAC_DROPBOX'
     and constraint_name = 'DRP_LOC_PROFILE_FK';

  if l_count = 0
  then
    execute immediate q'~
alter table orac_dropbox.drop_location add constraint drp_loc_profile_fk
  foreign key (processing_profile)
  references orac_dropbox.drop_processing_profile (profile_code)
    ~';
  end if;
end;
/
