--liquibase formatted sql

--changeset clive:post_install_orac_code_post_install_open_meteo_geocoder_acl context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: allow Orac schemas to reach the Open-Meteo geocoding endpoint

declare
  procedure reset_host_privilege(
    p_principal  in varchar2,
    p_privilege  in varchar2,
    p_lower_port in number default null,
    p_upper_port in number default null
  ) is
  begin
    begin
      dbms_network_acl_admin.remove_host_ace(
        host       => 'geocoding-api.open-meteo.com',
        lower_port => p_lower_port,
        upper_port => p_upper_port,
        ace        => xs$ace_type(
                        privilege_list => xs$name_list(p_privilege),
                        principal_name => p_principal,
                        principal_type => xs_acl.ptype_db
                      )
      );
    exception
      when others then
        if sqlcode not in (-24243, -46377, -1927) then
          raise;
        end if;
    end;

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
  end reset_host_privilege;
begin
  for rec in (
    select 'ORAC_CODE' as principal from dual
    union all
    select 'ORAC_APX_PUB' as principal from dual
  ) loop
    reset_host_privilege(
      p_principal  => rec.principal,
      p_privilege  => 'connect',
      p_lower_port => 443,
      p_upper_port => 443
    );
    reset_host_privilege(
      p_principal  => rec.principal,
      p_privilege  => 'http',
      p_lower_port => 443,
      p_upper_port => 443
    );
    reset_host_privilege(
      p_principal => rec.principal,
      p_privilege => 'resolve'
    );
  end loop;
end;
/

--rollback not required for idempotent post-install block; reversing it may remove shared external privileges.
