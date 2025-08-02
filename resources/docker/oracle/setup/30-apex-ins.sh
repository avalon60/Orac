# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# DAPEX script to install APEX on container setup.
#
PROG='30-apex-ins.sh'
LOG=`basename $0 .sh`.log
LOG=/var/tmp/dapex/log/${LOG}
E="-e"
if [ "$INC_APEX" = "FALSE" ]
then
  echo "${PROG} APEX install skipped (INC_APEX=${INC_APEX})."                        | tee -a ${LOG}
else
  echo "${PROG} Started." >> ${LOG}
  export APEX_HOME=/home/oracle/${ORACLE_PDB}/apex
  
  # Find the CDN for this release, using the cdn.dat mappings file.
  if [ -f "${ORACLE_BASE}/scripts/setup/cdn.dat" ]
  then
    CDN_REC=`cat ${ORACLE_BASE}/scripts/setup/cdn.dat | grep "^${APEX_VERS}:"`
  fi
  
  if [ -z "$CDN_REC" ]
  then
      echo "ERROR: No matching CDN record, for this version, in the deployed cdn.dat file!" |  tee -a ${LOG}
      exit 1
  else
      CDN=`echo ${CDN_REC} | sed "s/^${APEX_VERS}://"`
  fi
  
  echo "Starting APEX install" | tee -a ${LOG}
  cd ${APEX_HOME}
  
  sqlplus / as sysdba <<EOF | tee -a ${LOG}
  alter session set container=${ORACLE_PDB};
  
  -- Switch off password expiry
  alter profile DEFAULT limit password_life_time UNLIMITED;
  
  -- Install APEX in the PDB.
  alter session set container = ${ORACLE_PDB:-ORCLPDB1};
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
fi
echo "${PROG}: Done."                                                                    | tee -a ${LOG}
