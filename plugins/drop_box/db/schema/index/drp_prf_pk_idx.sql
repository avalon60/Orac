--liquibase formatted sql
declare
  l_count number;
begin
  select count(*)
    into l_count
    from all_indexes
   where owner = 'ORAC_DROPBOX'
     and index_name = 'DRP_PRF_PK_IDX';

  if l_count = 0
  then
    execute immediate
      'create unique index orac_dropbox.drp_prf_pk_idx on orac_dropbox.drop_processing_profile (profile_code)';
  end if;
end;
/
