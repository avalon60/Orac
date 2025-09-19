--------------------------------------------------------------------------------
-- INSTEAD OF TRIGGERS (for Views)
--------------------------------------------------------------------------------

-- iot: user_preferences_v_iud — normalize display value → JSON scalar; route DML to base table
create or replace trigger orac.user_preferences_v_iud
instead of insert or update or delete on orac.user_preferences_v
for each row
declare
  l_json_txt  clob;        -- JSON text to pass to json(...)
  l_bool_txt  varchar2(5);
  l_new_id    number;
begin
  if inserting or updating then
    if :new.value_type not in ('string','number','boolean') then
      raise_application_error(-20002, 'Unknown value_type: '||:new.value_type);
    end if;

    if :new.value_type = 'string' then
      l_json_txt := '"' || replace(nvl(:new.value_display,''), '"', '\"') || '"';
    elsif :new.value_type = 'number' then
      begin
        declare d number; begin d := to_number(trim(:new.value_display)); end;
      exception when others then
        raise_application_error(-20003, 'Invalid number: '||:new.value_display);
      end;
      l_json_txt := trim(:new.value_display);
    else
      l_bool_txt :=
        case lower(nvl(:new.value_display,'false'))
          when 'true' then 'true'
          when '1'    then 'true'
          when 'yes'  then 'true'
          when 'y'    then 'true'
          else 'false'
        end;
      l_json_txt := l_bool_txt;
    end if;
  end if;

  if inserting then
    insert into orac.user_preferences (user_id, pref_key, value_type, pref_value)
    values (:new.user_id, :new.pref_key, :new.value_type, json(l_json_txt))
    returning pref_id into l_new_id;
    -- NOTE: cannot assign :new.pref_id in INSTEAD OF trigger; allow APEX to re-query

  elsif updating then
    update orac.user_preferences
       set user_id    = :new.user_id,
           pref_key   = :new.pref_key,
           value_type = :new.value_type,
           pref_value = json(l_json_txt)
     where pref_id = :old.pref_id;

  elsif deleting then
    delete from orac.user_preferences
     where pref_id = :old.pref_id;
  end if;
end;
/

