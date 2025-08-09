# Author: Clive Bostock
#   Date: 9 Aug 2025
#
# Orac script to install APEX on container setup.
#
PROG='10-apex-ins.sh'
E="-e"
echo "${PROG} Started."   
export APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
export ORACLE_SID=${ORACLE_SID:-FREE}
export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}

# Derive the CDN for this release
CDN=" https://static.oracle.com/cdn/apex/${APEX_VERSION}.0/"

cd ${APEX_HOME}

echo "${PROG} Started"
echo "${PROG} Launching sqlplus; installing APEX..."
sqlplus / as sysdba <<EOF 
alter session set container=${ORACLE_PDB};

-- Switch off password expiry
alter profile DEFAULT limit password_life_time UNLIMITED;

-- Install APEX in the SID.
alter session set container = ${ORACLE_PDB:-FREE};
-- @apxremov.sql

@apexins.sql SYSAUX SYSAUX TEMP /i/

-- Set the APEX admin password.
begin
    apex_util.set_security_group_id( 10 );
    
    apex_util.create_user(
        p_user_name                    => 'ADMIN',
        p_email_address                => 'me@example.com',
        p_web_password                 => '${ORACLE_PWD}',
        p_developer_privs              => 'ADMIN',
        p_change_password_on_first_use => 'N' );
    apex_util.set_security_group_id( null );
    commit;
end;
/

-- Create the APEX_LISTENER and APEX_REST_PUBLIC_USER users
@apex_rest_config.sql ${ORACLE_PWD} ${ORACLE_PWD}

-- Unlock the accounts.
alter user ANONYMOUS account unlock;
alter user APEX_REST_PUBLIC_USER  account unlock;
alter user APEX_PUBLIC_USER account unlock;
alter user ORDS_PUBLIC_USER account unlock;
alter user APEX_LISTENER account unlock;
@${APEX_HOME}/utilities/reset_image_prefix_core.sql ${CDN} x
@${ORACLE_BASE}/scripts/setup/apex_check.sql
EOF
echo "${PROG}: Done."     
