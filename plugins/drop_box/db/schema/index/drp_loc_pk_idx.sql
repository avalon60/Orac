--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_indexes where owner = 'ORAC_DROPBOX' and index_name = 'DRP_LOC_PK_IDX';
  if l_count = 0 then
    execute immediate 'create unique index orac_dropbox.drp_loc_pk_idx on orac_dropbox.drop_location (drop_location_id)';
  end if;
end;
/
