--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_PK';
  if l_count = 0 then
    execute immediate 'alter table orac_dropbox.drop_location add constraint drp_loc_pk primary key (drop_location_id) using index orac_dropbox.drp_loc_pk_idx';
  end if;
end;
/
