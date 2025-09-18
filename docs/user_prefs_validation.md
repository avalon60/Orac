
Totally with you—`value_type` gets you part-way, but you’ll want **per-key validation** so junk can’t land in `pref_value`. Here’s a clean, database-centric pattern that works well with APEX and your current JSON design:

---

# 1) Whitelist keys (+ types) in a reference table

```sql
-- table: orac.pref_keys — authoritative list of allowed keys + expected value_type
create table orac.pref_keys (
  pref_key     varchar2(100) primary key,
  value_type   varchar2(8)   not null check (value_type in ('string','number','boolean')),
  description  varchar2(4000)
);

-- seed the keys you listed (adjust descriptions as you like)
insert into orac.pref_keys (pref_key, value_type, description) values ('date_format',          'string',  'oracle date format model');
insert into orac.pref_keys (pref_key, value_type, description) values ('timezone',             'string',  'iana timezone, e.g. Europe/London');
insert into orac.pref_keys (pref_key, value_type, description) values ('theme_style',          'string',  'apex theme style');
insert into orac.pref_keys (pref_key, value_type, description) values ('landing_page_id',      'number',  'default landing page id');
insert into orac.pref_keys (pref_key, value_type, description) values ('rows_per_report',      'number',  'pagination size');
insert into orac.pref_keys (pref_key, value_type, description) values ('email_opt_in',         'boolean', 'email notifications');
insert into orac.pref_keys (pref_key, value_type, description) values ('push_opt_in',          'boolean', 'push notifications');
insert into orac.pref_keys (pref_key, value_type, description) values ('tts_voice',            'string',  'voice id');
insert into orac.pref_keys (pref_key, value_type, description) values ('tts_rate',             'number',  'speech rate multiplier');
insert into orac.pref_keys (pref_key, value_type, description) values ('tts_pitch',            'number',  'speech pitch');
insert into orac.pref_keys (pref_key, value_type, description) values ('default_llm_id',       'number',  'fk to orac.llm_registry.llm_id or null');
insert into orac.pref_keys (pref_key, value_type, description) values ('temperature',          'number',  'sampling temperature');
insert into orac.pref_keys (pref_key, value_type, description) values ('max_tokens',           'number',  'output cap (soft)');
insert into orac.pref_keys (pref_key, value_type, description) values ('strip_reasoning_tags', 'boolean', 'remove <reasoning>..</reasoning>');
insert into orac.pref_keys (pref_key, value_type, description) values ('show_reasoning',       'boolean', 'surface hidden reasoning');
insert into orac.pref_keys (pref_key, value_type, description) values ('force_concise',        'boolean', 'prefer concise replies');
insert into orac.pref_keys (pref_key, value_type, description) values ('enable_feedback',      'boolean', 'user feedback prompts');
insert into orac.pref_keys (pref_key, value_type, description) values ('enable_advanced_mode', 'boolean', 'unlock expert features');

commit;
```

Add a real **foreign key** from `user_preferences.pref_key` to this list so only known keys are accepted:

```sql
alter table orac.user_preferences
  add constraint usrprf_prefkeys_fk1
  foreign key (pref_key) references orac.pref_keys (pref_key);
```

> This gives you hard control over which keys exist, independent of UI.

---

# 2) Time zone validation source

Two options:

**A. Lightweight local table (no extra privileges):**

```sql
create table orac.timezones (
  tz_name varchar2(80) primary key
);

-- seed a reasonable starter set; expand as you like
insert into orac.timezones values ('UTC');
insert into orac.timezones values ('Europe/London');
insert into orac.timezones values ('Europe/Paris');
insert into orac.timezones values ('America/New_York');
insert into orac.timezones values ('America/Los_Angeles');
insert into orac.timezones values ('Asia/Tokyo');
insert into orac.timezones values ('Australia/Sydney');
commit;
```

**B. Populate from Oracle’s catalog (needs grant to `v$timezone_names`):**

```sql
-- as SYS (or with suitable catalog privileges), once:
grant select on v_$timezone_names to orac;

-- as ORAC:
insert /*+ ignore_row_on_dupkey_index(orac.timezones)(tz_name) */
into orac.timezones (tz_name)
select distinct tzname
from v$timezone_names
where instr(tzname,'/') > 0
  and tzname not like 'Etc/%';

commit;
```

APEX can use this table as an LOV for a select list, and the DB will still validate server-side.

---

# 3) Central, server-side validation (trigger)

This trigger runs on the **base table**, so it works whether you write through your view or directly. It validates the **semantics** per key and also ensures `value_type` matches the definition in `orac.pref_keys`.

```sql
create or replace trigger orac.user_prefs_chk_biu
before insert or update on orac.user_preferences
for each row
declare
  l_str   varchar2(4000);
  l_num   number;
  l_bool  varchar2(5);
  l_vtype orac.pref_keys.value_type%type;
  l_cnt   integer;
begin
  -- 1) pref_key must exist (FK ensures this), and value_type must match the master definition
  select value_type into l_vtype
  from orac.pref_keys
  where pref_key = :new.pref_key;

  if :new.value_type <> l_vtype then
    raise_application_error(-20050,
      'invalid value_type "'||:new.value_type||
      '" for key "'||:new.pref_key||'"; expected "'||l_vtype||'".');
  end if;

  -- 2) Extract the scalar from JSON according to type (your CHECK already guards this)
  if :new.value_type = 'string' then
    select json_value(:new.pref_value, '$' returning varchar2(4000) null on error)
      into l_str from dual;

  elsif :new.value_type = 'number' then
    select json_value(:new.pref_value, '$' returning number null on error)
      into l_num from dual;

  else -- boolean
    select lower(json_value(:new.pref_value, '$' returning varchar2(5) null on error))
      into l_bool from dual;
    if l_bool not in ('true','false') then
      raise_application_error(-20051, 'boolean must be true or false.');
    end if;
  end if;

  -- 3) Per-key semantic validation
  case :new.pref_key
    when 'timezone' then
      select count(*) into l_cnt from orac.timezones where tz_name = l_str;
      if l_cnt = 0 then
        raise_application_error(-20060,
          'invalid timezone "'||nvl(l_str,'(null)')||
          '". choose a valid IANA zone, e.g. Europe/London.');
      end if;

    when 'date_format' then
      begin
        declare v_dummy varchar2(200); begin
          select to_char(systimestamp, l_str) into v_dummy from dual;
        end;
      exception when others then
        raise_application_error(-20061,
          'invalid date format model "'||nvl(l_str,'(null)')||'".');
      end;

    when 'rows_per_report' then
      if l_num is null or l_num < 5 or l_num > 500 then
        raise_application_error(-20062,
          'rows_per_report must be between 5 and 500.');
      end if;

    when 'temperature' then
      if l_num is null or l_num < 0 or l_num > 2 then
        raise_application_error(-20063, 'temperature must be between 0.0 and 2.0.');
      end if;

    when 'max_tokens' then
      if l_num is null or l_num < 1 or l_num > 32768 then
        raise_application_error(-20064,
          'max_tokens must be between 1 and 32768.');
      end if;

    when 'default_llm_id' then
      if l_num is not null then
        select count(*) into l_cnt from orac.llm_registry where llm_id = l_num;
        if l_cnt = 0 then
          raise_application_error(-20065,
            'default_llm_id '||l_num||' does not exist in orac.llm_registry.');
        end if;
      end if;

    when 'tts_rate' then
      if l_num is null or l_num < 0.5 or l_num > 1.5 then
        raise_application_error(-20066, 'tts_rate must be between 0.5 and 1.5.');
      end if;

    when 'tts_pitch' then
      if l_num is null or l_num < -12 or l_num > 12 then
        raise_application_error(-20067, 'tts_pitch must be between -12 and 12 semitones.');
      end if;

    when 'tts_voice' then
      -- simple sanity check; tighten if you have an allow-list
      if l_str is null or length(l_str) < 3 then
        raise_application_error(-20068, 'tts_voice must be a non-empty voice id.');
      end if;

    -- booleans below are type-validated already; nothing extra to do unless you want policy checks
    when 'email_opt_in'         then null;
    when 'push_opt_in'          then null;
    when 'strip_reasoning_tags' then null;
    when 'show_reasoning'       then null;
    when 'force_concise'        then null;
    when 'enable_feedback'      then null;
    when 'enable_advanced_mode' then null;

    when 'theme_style' then
      -- optionally enforce against a known list of APEX theme styles
      null;

    when 'landing_page_id' then
      -- optionally check the page exists in your app
      null;

    else
      -- future keys: leave permissive (you can add cases as you define new keys)
      null;
  end case;
end;
/
```

> This keeps **all correctness rules in the database** (APEX can still run its own validations, but the DB is the source of truth).

---

# 4) How this fits your existing view

Your `orac.user_preferences_v` + INSTEAD OF trigger can continue doing the **string/number/boolean UX normalization**. When that view inserts into `orac.user_preferences`, the **base trigger above fires** and blocks invalid values. So you don’t have to duplicate rules in multiple places.

---

# 5) Optional: APEX UX niceties

* **Timezone item**: Select List with LOV
  `select tz_name d, tz_name r from orac.timezones order by 1`
* **Date format item**: Text field + APEX validation calling

  ```sql
  declare v varchar2(200);
  begin
    select to_char(systimestamp, :PXX_DATE_FORMAT) into v from dual;
    return true;
  exception when others then
    return false;
  end;
  ```

  (DB trigger will still enforce; this just gives instant UI feedback.)
* **Numeric ranges**: Min/Max on APEX items *and* rely on DB trigger for final enforcement.

---

## Why this approach?

* **Strong control**: `pref_keys` + FK ensures only known keys exist.
* **Single source of truth**: one trigger validates semantics for all writers (APEX, scripts, API).
* **Extensible**: add new keys in `pref_keys`, then add a `when 'new_key' then …` case.
* **Friendly errors**: `raise_application_error` messages surface nicely in APEX forms.

If you want to go even further later, we can add a generalized `pref_defs` table (with `validator_kind`, `min_value`, `max_value`, `regex`, `allow_values JSON`, etc.) and have the trigger drive entirely from data. But the code above gets you robust, immediate protection for the keys you already have.
