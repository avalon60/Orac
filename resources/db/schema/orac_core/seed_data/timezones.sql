--liquibase formatted sql

--changeset clive:seed_orac_core_timezone_group_domain context:core labels:core stripComments:false runOnChange:true
merge into orac_core.domain_codes dst
using (
  select 'TIMEZONE_GROUP' domain_code
       , 'Timezone group' display_name
       , 'Geographical grouping used to organise the curated timezone selector.' description
       , 'Y' active_yn
       , 'Y' system_required_yn
    from dual
) src
on (dst.domain_code = src.domain_code)
when matched then update set
  dst.display_name = src.display_name,
  dst.description = src.description,
  dst.active_yn = src.active_yn,
  dst.system_required_yn = src.system_required_yn
when not matched then insert
(
  domain_code,
  display_name,
  description,
  active_yn,
  system_required_yn
)
values
(
  src.domain_code,
  src.display_name,
  src.description,
  src.active_yn,
  src.system_required_yn
);

--rollback select 1 from dual;

--changeset clive:seed_orac_core_timezone_group_values context:core labels:core stripComments:false runOnChange:true
merge into orac_core.domain_ref_values dst
using (
  select 'TIMEZONE_GROUP' domain_code, 'AFRICA' ref_value_code, 'Africa' display_value, 10 display_sequence from dual
  union all select 'TIMEZONE_GROUP', 'ASIA', 'Asia', 20 from dual
  union all select 'TIMEZONE_GROUP', 'EUROPE', 'Europe', 30 from dual
  union all select 'TIMEZONE_GROUP', 'GLOBAL', 'Global', 40 from dual
  union all select 'TIMEZONE_GROUP', 'NORTH_AMERICA', 'North America', 50 from dual
  union all select 'TIMEZONE_GROUP', 'OCEANIA', 'Oceania', 60 from dual
) src
on (
  dst.domain_code = src.domain_code
  and dst.ref_value_code = src.ref_value_code
)
when matched then update set
  dst.parent_domain_code = null,
  dst.parent_ref_value_code = null,
  dst.display_value = src.display_value,
  dst.description = 'Geographical grouping for curated timezone values.',
  dst.display_sequence = src.display_sequence,
  dst.icon = null,
  dst.color = null,
  dst.active_yn = 'Y',
  dst.system_required_yn = 'Y'
when not matched then insert
(
  domain_code,
  ref_value_code,
  parent_domain_code,
  parent_ref_value_code,
  display_value,
  description,
  display_sequence,
  icon,
  color,
  active_yn,
  system_required_yn
)
values
(
  src.domain_code,
  src.ref_value_code,
  null,
  null,
  src.display_value,
  'Geographical grouping for curated timezone values.',
  src.display_sequence,
  null,
  null,
  'Y',
  'Y'
);

--rollback select 1 from dual;

--changeset clive:seed_orac_core_timezone_domain context:core labels:core stripComments:false runOnChange:true
merge into orac_core.domain_codes dst
using (
  select 'TIMEZONE' domain_code
       , 'Timezone' display_name
       , 'Curated IANA timezone identifiers available for user preferences.' description
       , 'Y' active_yn
       , 'Y' system_required_yn
    from dual
) src
on (dst.domain_code = src.domain_code)
when matched then update set
  dst.display_name = src.display_name,
  dst.description = src.description,
  dst.active_yn = src.active_yn,
  dst.system_required_yn = src.system_required_yn
when not matched then insert
(
  domain_code,
  display_name,
  description,
  active_yn,
  system_required_yn
)
values
(
  src.domain_code,
  src.display_name,
  src.description,
  src.active_yn,
  src.system_required_yn
);

--rollback select 1 from dual;

--changeset clive:seed_orac_core_timezone_values context:core labels:core stripComments:false runOnChange:true
merge into orac_core.domain_ref_values dst
using (
  select 'Africa/Johannesburg' ref_value_code, 'Johannesburg (South Africa)' display_value, 'AFRICA' parent_ref_value_code, 1010 display_sequence from dual
  union all select 'Africa/Nairobi', 'Nairobi (East Africa)', 'AFRICA', 1020 from dual
  union all select 'Africa/Windhoek', 'Windhoek (Namibia)', 'AFRICA', 1030 from dual
  union all select 'Asia/Bangkok', 'Bangkok (Thailand)', 'ASIA', 2010 from dual
  union all select 'Asia/Dubai', 'Dubai (UAE)', 'ASIA', 2020 from dual
  union all select 'Asia/Hong_Kong', 'Hong Kong', 'ASIA', 2030 from dual
  union all select 'Asia/Karachi', 'Karachi (Pakistan)', 'ASIA', 2040 from dual
  union all select 'Asia/Kolkata', 'Kolkata (India)', 'ASIA', 2050 from dual
  union all select 'Asia/Riyadh', 'Riyadh (Saudi Arabia)', 'ASIA', 2060 from dual
  union all select 'Asia/Seoul', 'Seoul (South Korea)', 'ASIA', 2070 from dual
  union all select 'Asia/Shanghai', 'Shanghai (China)', 'ASIA', 2080 from dual
  union all select 'Asia/Singapore', 'Singapore', 'ASIA', 2090 from dual
  union all select 'Asia/Tokyo', 'Tokyo (Japan)', 'ASIA', 2100 from dual
  union all select 'Europe/Amsterdam', 'Amsterdam (Netherlands)', 'EUROPE', 3010 from dual
  union all select 'Europe/Berlin', 'Berlin (Germany)', 'EUROPE', 3020 from dual
  union all select 'Europe/Dublin', 'Dublin (Ireland)', 'EUROPE', 3030 from dual
  union all select 'Europe/Helsinki', 'Helsinki (Finland)', 'EUROPE', 3040 from dual
  union all select 'Europe/Lisbon', 'Lisbon (Portugal)', 'EUROPE', 3050 from dual
  union all select 'Europe/London', 'London (UK)', 'EUROPE', 3060 from dual
  union all select 'Europe/Madrid', 'Madrid (Spain)', 'EUROPE', 3070 from dual
  union all select 'Europe/Paris', 'Paris (France)', 'EUROPE', 3080 from dual
  union all select 'Europe/Rome', 'Rome (Italy)', 'EUROPE', 3090 from dual
  union all select 'Europe/Warsaw', 'Warsaw (Poland)', 'EUROPE', 3100 from dual
  union all select 'UTC', 'UTC', 'GLOBAL', 4010 from dual
  union all select 'America/Anchorage', 'Anchorage (Alaska)', 'NORTH_AMERICA', 5010 from dual
  union all select 'America/Chicago', 'Chicago (US Central)', 'NORTH_AMERICA', 5020 from dual
  union all select 'America/Denver', 'Denver (US Mountain)', 'NORTH_AMERICA', 5030 from dual
  union all select 'America/Halifax', 'Halifax (Atlantic Canada)', 'NORTH_AMERICA', 5040 from dual
  union all select 'America/Los_Angeles', 'Los Angeles (US Pacific)', 'NORTH_AMERICA', 5050 from dual
  union all select 'America/New_York', 'New York (US Eastern)', 'NORTH_AMERICA', 5060 from dual
  union all select 'America/Phoenix', 'Phoenix (Arizona)', 'NORTH_AMERICA', 5070 from dual
  union all select 'America/Toronto', 'Toronto (Canada Eastern)', 'NORTH_AMERICA', 5080 from dual
  union all select 'America/Vancouver', 'Vancouver (Canada Pacific)', 'NORTH_AMERICA', 5090 from dual
  union all select 'Australia/Adelaide', 'Adelaide (Australia Central)', 'OCEANIA', 6010 from dual
  union all select 'Australia/Brisbane', 'Brisbane (Australia Eastern)', 'OCEANIA', 6020 from dual
  union all select 'Australia/Perth', 'Perth (Australia Western)', 'OCEANIA', 6030 from dual
  union all select 'Australia/Sydney', 'Sydney (Australia Eastern)', 'OCEANIA', 6040 from dual
  union all select 'Pacific/Auckland', 'Auckland (New Zealand)', 'OCEANIA', 6050 from dual
) src
on (
  dst.domain_code = 'TIMEZONE'
  and dst.ref_value_code = src.ref_value_code
)
when matched then update set
  dst.parent_domain_code = 'TIMEZONE_GROUP',
  dst.parent_ref_value_code = src.parent_ref_value_code,
  dst.display_value = src.display_value,
  dst.description = 'Curated IANA timezone identifier.',
  dst.display_sequence = src.display_sequence,
  dst.icon = null,
  dst.color = null,
  dst.active_yn = 'Y',
  dst.system_required_yn = 'Y'
when not matched then insert
(
  domain_code,
  ref_value_code,
  parent_domain_code,
  parent_ref_value_code,
  display_value,
  description,
  display_sequence,
  icon,
  color,
  active_yn,
  system_required_yn
)
values
(
  'TIMEZONE',
  src.ref_value_code,
  'TIMEZONE_GROUP',
  src.parent_ref_value_code,
  src.display_value,
  'Curated IANA timezone identifier.',
  src.display_sequence,
  null,
  null,
  'Y',
  'Y'
);

--rollback select 1 from dual;
