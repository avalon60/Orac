--liquibase formatted sql
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_ENABLED_CK';
  if l_count = 0 then
    execute immediate q'~alter table orac_dropbox.drop_location add constraint drp_loc_enabled_ck check (enabled_yn in ('Y', 'N'))~';
  end if;
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_RECURSIVE_CK';
  if l_count = 0 then
    execute immediate q'~alter table orac_dropbox.drop_location add constraint drp_loc_recursive_ck check (recursive_yn in ('Y', 'N'))~';
  end if;
  select count(*) into l_count from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_MOVE_CK';
  if l_count = 0 then
    execute immediate q'~alter table orac_dropbox.drop_location add constraint drp_loc_move_ck check (move_processed_yn in ('Y', 'N'))~';
  end if;
end;
/
