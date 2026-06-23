--liquibase formatted sql

--changeset clive:seed_data_orac_core_seed_data_tmzone_timezone_catalog context:core labels:core stripComments:false runOnChange:true
merge into orac_core.timezones tgt
using (
  select 'Africa/Johannesburg' as tz_name, 'Johannesburg (South Africa)' as display_label, 'Africa' as region_group, 10 as display_sequence, 'Y' as is_active from dual
  union all select 'Africa/Nairobi', 'Nairobi (East Africa)', 'Africa', 20, 'Y' from dual
  union all select 'Africa/Windhoek', 'Windhoek (Namibia)', 'Africa', 30, 'Y' from dual
  union all select 'America/Anchorage', 'Anchorage (Alaska)', 'North America', 10, 'Y' from dual
  union all select 'America/Chicago', 'Chicago (US Central)', 'North America', 20, 'Y' from dual
  union all select 'America/Denver', 'Denver (US Mountain)', 'North America', 30, 'Y' from dual
  union all select 'America/Halifax', 'Halifax (Atlantic Canada)', 'North America', 40, 'Y' from dual
  union all select 'America/Los_Angeles', 'Los Angeles (US Pacific)', 'North America', 50, 'Y' from dual
  union all select 'America/New_York', 'New York (US Eastern)', 'North America', 60, 'Y' from dual
  union all select 'America/Phoenix', 'Phoenix (Arizona)', 'North America', 70, 'Y' from dual
  union all select 'America/Toronto', 'Toronto (Canada Eastern)', 'North America', 80, 'Y' from dual
  union all select 'America/Vancouver', 'Vancouver (Canada Pacific)', 'North America', 90, 'Y' from dual
  union all select 'Asia/Bangkok', 'Bangkok (Thailand)', 'Asia', 10, 'Y' from dual
  union all select 'Asia/Dubai', 'Dubai (UAE)', 'Asia', 20, 'Y' from dual
  union all select 'Asia/Hong_Kong', 'Hong Kong', 'Asia', 30, 'Y' from dual
  union all select 'Asia/Karachi', 'Karachi (Pakistan)', 'Asia', 40, 'Y' from dual
  union all select 'Asia/Kolkata', 'Kolkata (India)', 'Asia', 50, 'Y' from dual
  union all select 'Asia/Riyadh', 'Riyadh (Saudi Arabia)', 'Asia', 60, 'Y' from dual
  union all select 'Asia/Seoul', 'Seoul (South Korea)', 'Asia', 70, 'Y' from dual
  union all select 'Asia/Shanghai', 'Shanghai (China)', 'Asia', 80, 'Y' from dual
  union all select 'Asia/Singapore', 'Singapore', 'Asia', 90, 'Y' from dual
  union all select 'Asia/Tokyo', 'Tokyo (Japan)', 'Asia', 100, 'Y' from dual
  union all select 'Australia/Adelaide', 'Adelaide (Australia Central)', 'Oceania', 10, 'Y' from dual
  union all select 'Australia/Brisbane', 'Brisbane (Australia Eastern)', 'Oceania', 20, 'Y' from dual
  union all select 'Australia/Perth', 'Perth (Australia Western)', 'Oceania', 30, 'Y' from dual
  union all select 'Australia/Sydney', 'Sydney (Australia Eastern)', 'Oceania', 40, 'Y' from dual
  union all select 'Europe/Amsterdam', 'Amsterdam (Netherlands)', 'Europe', 10, 'Y' from dual
  union all select 'Europe/Berlin', 'Berlin (Germany)', 'Europe', 20, 'Y' from dual
  union all select 'Europe/Dublin', 'Dublin (Ireland)', 'Europe', 30, 'Y' from dual
  union all select 'Europe/Helsinki', 'Helsinki (Finland)', 'Europe', 40, 'Y' from dual
  union all select 'Europe/Lisbon', 'Lisbon (Portugal)', 'Europe', 50, 'Y' from dual
  union all select 'Europe/London', 'London (UK)', 'Europe', 60, 'Y' from dual
  union all select 'Europe/Madrid', 'Madrid (Spain)', 'Europe', 70, 'Y' from dual
  union all select 'Europe/Paris', 'Paris (France)', 'Europe', 80, 'Y' from dual
  union all select 'Europe/Rome', 'Rome (Italy)', 'Europe', 90, 'Y' from dual
  union all select 'Europe/Warsaw', 'Warsaw (Poland)', 'Europe', 100, 'Y' from dual
  union all select 'Pacific/Auckland', 'Auckland (New Zealand)', 'Oceania', 50, 'Y' from dual
  union all select 'UTC', 'UTC', 'Global', 10, 'Y' from dual
) src
on (tgt.tz_name = src.tz_name)
when matched then update set
  tgt.display_label = src.display_label,
  tgt.region_group = src.region_group,
  tgt.display_sequence = src.display_sequence,
  tgt.is_active = src.is_active
when not matched then insert
(
  tz_name,
  display_label,
  region_group,
  display_sequence,
  is_active
)
values
(
  src.tz_name,
  src.display_label,
  src.region_group,
  src.display_sequence,
  src.is_active
)
;

--rollback delete from orac_core.timezones where tz_name in ('Africa/Johannesburg', 'Africa/Nairobi', 'Africa/Windhoek', 'America/Anchorage', 'America/Chicago', 'America/Denver', 'America/Halifax', 'America/Los_Angeles', 'America/New_York', 'America/Phoenix', 'America/Toronto', 'America/Vancouver', 'Asia/Bangkok', 'Asia/Dubai', 'Asia/Hong_Kong', 'Asia/Karachi', 'Asia/Kolkata', 'Asia/Riyadh', 'Asia/Seoul', 'Asia/Shanghai', 'Asia/Singapore', 'Asia/Tokyo', 'Australia/Adelaide', 'Australia/Brisbane', 'Australia/Perth', 'Australia/Sydney', 'Europe/Amsterdam', 'Europe/Berlin', 'Europe/Dublin', 'Europe/Helsinki', 'Europe/Lisbon', 'Europe/London', 'Europe/Madrid', 'Europe/Paris', 'Europe/Rome', 'Europe/Warsaw', 'Pacific/Auckland', 'UTC');
