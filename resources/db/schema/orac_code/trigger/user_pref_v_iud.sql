--liquibase formatted sql

--changeset clive:create_trigger_orac_code_trigger_user_pref_v_iud context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-26
-- __description__: writable support for the ORAC_CODE user preferences maintenance view

create or replace trigger orac_code.user_pref_v_iud
instead of insert or update or delete on orac_code.user_preferences_v
for each row
declare
  l_pref_id          orac_api.user_preferences_v.pref_id%type;
  l_row_version      orac_api.user_preferences_v.row_version%type;
  l_pref_value_text  varchar2(32767);
begin
  if inserting or updating then
    if :new.pref_value is not null then
      l_pref_value_text := json_serialize(:new.pref_value returning varchar2);
    end if;

    if :new.value_type not in ('string', 'number', 'boolean', 'json') then
      raise_application_error(-20002, 'Unknown value_type: ' || :new.value_type);
    end if;

    if :new.value_type = 'number' then
      begin
        declare
          l_number_value number;
        begin
          l_number_value := to_number(trim(l_pref_value_text));
        end;
      exception
        when others then
          raise_application_error(-20003, 'Invalid number: ' || l_pref_value_text);
      end;
    elsif :new.value_type = 'boolean' then
      if lower(nvl(l_pref_value_text, 'false')) not in ('true', 'false', '1', '0', 'yes', 'no', 'y', 'n') then
        raise_application_error(-20004, 'Invalid boolean: ' || l_pref_value_text);
      end if;
    end if;
  end if;

  if inserting then
    l_pref_id := null;

    orac_code.user_preferences_api.ins(
      p_pref_id     => l_pref_id,
      p_user_id     => :new.user_id,
      p_pref_key    => :new.pref_key,
      p_pref_value  => :new.pref_value,
      p_value_type  => :new.value_type,
      p_row_version => l_row_version
    );
  elsif updating then
    l_pref_id := :old.pref_id;

    orac_code.user_preferences_api.upd(
      p_pref_id     => l_pref_id,
      p_user_id     => :new.user_id,
      p_pref_key    => :new.pref_key,
      p_pref_value  => :new.pref_value,
      p_value_type  => :new.value_type,
      p_row_version => l_row_version
    );
  elsif deleting then
    l_pref_id := :old.pref_id;

    orac_code.user_preferences_api.del(
      p_pref_id     => l_pref_id,
      p_row_version => l_row_version
    );
  end if;
end;
/

--rollback drop trigger orac_code.user_pref_v_iud;
