--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_CODE_UK';
  if l_count = 0 then
    execute immediate 'alter table orac_dropbox.drop_location add constraint drp_loc_code_uk unique (location_code)';
  end if;
end;
/
