-- __author__: clive
-- __date__: 2026-04-25
-- __description__: writable support for the published user preferences view

create or replace trigger orac_api.user_preferences_v_iud
instead of insert or update or delete on orac_api.user_preferences_v
for each row
declare
begin
  if inserting or updating then
    if :new.value_type not in ('string', 'number', 'boolean') then
      raise_application_error(-20002, 'Unknown value_type: ' || :new.value_type);
    end if;

    if :new.value_type = 'number' then
      begin
        declare
          l_number_value number;
        begin
          l_number_value := to_number(trim(:new.pref_value));
        end;
      exception
        when others then
          raise_application_error(-20003, 'Invalid number: ' || :new.pref_value);
      end;
    elsif :new.value_type = 'boolean' then
      if lower(nvl(:new.pref_value, 'false')) not in ('true', 'false', '1', '0', 'yes', 'no', 'y', 'n') then
        raise_application_error(-20004, 'Invalid boolean: ' || :new.pref_value);
      end if;
    end if;
  end if;

  if inserting then
    insert into orac.user_preferences (user_id, pref_key, value_type, pref_value)
    values (:new.user_id, :new.pref_key, :new.value_type, :new.pref_value);

  elsif updating then
    update orac.user_preferences
       set user_id = :new.user_id,
           pref_key = :new.pref_key,
           value_type = :new.value_type,
           pref_value = :new.pref_value
     where pref_id = :old.pref_id;

  elsif deleting then
    delete from orac.user_preferences
     where pref_id = :old.pref_id;
  end if;
end;
/
