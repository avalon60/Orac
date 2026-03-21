-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create table orac.devices (
  device_id   varchar2(128 char) not null,
  user_id     number not null,
  host_name   varchar2(255 char),
  is_active   char(1) default 'y' not null,
  created_on  timestamp(6) with local time zone default on null systimestamp not null,
  created_by  varchar2(128 char) default on null sys_context('userenv','session_user') not null,
  updated_on  timestamp(6) with local time zone,
  updated_by  varchar2(128 char),
  row_version number default 1 not null
);
