-- __author__: clive
-- __date__: 2026-04-27
-- __description__: allow Orac schemas to reach the Open-Meteo geocoding endpoint

declare
  procedure ensure_host_privilege(
    p_principal  in varchar2,
    p_privilege  in varchar2,
    p_lower_port in number default null,
    p_upper_port in number default null
  ) is
    l_granted number;
  begin
    select count(*)
      into l_granted
      from dba_network_acls a
      join dba_network_acl_privileges p
        on p.acl = a.acl
     where a.host = 'geocoding-api.open-meteo.com'
       and (p_lower_port is null or a.lower_port = p_lower_port)
       and (p_upper_port is null or a.upper_port = p_upper_port)
       and p.principal = p_principal
       and p.privilege = p_privilege
       and p.is_grant = 'true';

    if l_granted = 0 then
      dbms_network_acl_admin.append_host_ace(
        host       => 'geocoding-api.open-meteo.com',
        lower_port => p_lower_port,
        upper_port => p_upper_port,
        ace        => xs$ace_type(
                        privilege_list => xs$name_list(p_privilege),
                        principal_name => p_principal,
                        principal_type => xs_acl.ptype_db
                      )
      );
    end if;
  end ensure_host_privilege;
begin
  for rec in (
    select 'ORAC_CODE' as principal from dual
    union all
    select 'ORAC_APX_PUB' as principal from dual
  ) loop
    ensure_host_privilege(
      p_principal  => rec.principal,
      p_privilege  => 'connect',
      p_lower_port => 443,
      p_upper_port => 443
    );
    ensure_host_privilege(
      p_principal  => rec.principal,
      p_privilege  => 'http',
      p_lower_port => 443,
      p_upper_port => 443
    );
    ensure_host_privilege(
      p_principal => rec.principal,
      p_privilege => 'resolve'
    );
  end loop;
end;
/
