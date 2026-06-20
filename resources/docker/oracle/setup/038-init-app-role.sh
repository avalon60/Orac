# Author: Clive Bostock
#   Date: 15 Mar 2026
#
# Orac script to add ADMINISTRATOR role etc. for the ORAC_ADMIN user.
#
# 038-init-app-role.sql
#
PROG="Orac: 038-init-app-role.sh"
E="-e"

export APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
export ORACLE_SID=${ORACLE_SID:-FREE}
export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
echo "[$(timestamp)] ${PROG} Started"

if [[ -z "${ORACLE_PWD:-}" ]]; then
    echo "ORAC_APEX_ADMIN_SETUP_FAILED: ORACLE_PWD is not set."
    return 1 2>/dev/null || exit 1
fi

# Derive the CDN for this release
CDN=" https://static.oracle.com/cdn/apex/${APEX_VERSION}.0/"

cd ${APEX_HOME}

echo "${PROG} Launching sqlplus; installing APEX..."
sqlplus / as sysdba <<EOF 
alter session set container=${ORACLE_PDB};

begin
    -- 1. Tell APEX which workspace you are working in
    -- Use 'ORAC' (based on your footer in the first screenshot)
    apex_util.set_workspace(p_workspace => 'ORAC'); 

    -- 2. Reset and enable the exported workspace account for this install.
    apex_util.reset_password (
        p_user_name                    => 'ORAC_ADMIN',
        p_new_password                 => '${ORACLE_PWD}',
        p_change_password_on_first_use => false
    );

    apex_util.unlock_account (
        p_user_name => 'ORAC_ADMIN'
    );

    apex_util.unexpire_workspace_account (
        p_user_name => 'ORAC_ADMIN'
    );

    -- 3. Grant the role
    apex_acl.add_user_role (
        p_application_id => 1042,
        p_user_name      => 'ORAC_ADMIN',
        p_role_static_id => 'ADMINISTRATOR'
    );


    apex_acl.add_user_role (
        p_application_id => 1042,
        p_user_name      => 'ORAC_ADMIN',
        p_role_static_id => 'CONTRIBUTOR'
    );


    apex_acl.add_user_role (
        p_application_id => 1042,
        p_user_name      => 'ORAC_ADMIN',
        p_role_static_id => 'READER'
    );

    commit;
end;
/
EOF
echo "[$(timestamp)] ${PROG}: Done."     
