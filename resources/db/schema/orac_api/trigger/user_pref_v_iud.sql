-- __author__: clive
-- __date__: 2026-04-26
-- __description__: retire the obsolete ORAC_API user preferences writable trigger

begin
  execute immediate 'drop trigger orac_api.user_pref_v_iud';
exception
  when others then
    if sqlcode != -4080 then
      raise;
    end if;
end;
/
