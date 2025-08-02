#!/usr/bin/env bash
#
# Docker4APEX
#
# update-glogin.sh
#
# Updates the sqlplus glogin.sql file, appending
# Docker4APEX add-on settings as per the
# <DAPEX_HOME>/deploy/etc/glogin.template file.
#
# Set locations within the container...
DAPEX_BASE=/var/tmp/dapex
DAPEX_BIN=${DAPEX_BASE}/etc
DAPEX_ETC=${DAPEX_BASE}/etc
SQLPLUS_GLOGIN=`find $ORACLE_HOME -name glogin.sql`

# Try get the container name from the container.reg file.
# Failing that we fall back to using the ${ORACLE_SID}.
# Unless something has gone wrong, the last two steps shouldn't be 
# needed.
if [ -f "${DAPEX_ETC}/container.reg" ]
then
  echo "Using Container name from registry file..."
  CONTAINER_NAME=`cat ${DAPEX_ETC}/container.reg | grep "^CONTAINER_NAME:" | cut -d":" -f2` 
else
  echo "Falling back to ORACLE_SID ..."
  CONTAINER_NAME=${ORACLE_SID}
fi

if [ -f "${SQLPLUS_GLOGIN}" ]
then
  DAPEX_EDITED=`grep '\-\-\- Docker4APEX' ${SQLPLUS_GLOGIN}`
  if [ -z "${DAPEX_EDITED}" ]
  then
    echo -e "Updating SQLPlus glogin file at:\n ${SQLPLUS_GLOGIN}"
    cat ${DAPEX_ETC}/glogin.template | sed "s/%CONTAINER_NAME%/${CONTAINER_NAME}/" >> ${SQLPLUS_GLOGIN}
    echo -e "Modification complete."
  else
    echo -e "Previous SQLPlus glogin edits, for Docker4APEX detected..."
    echo -e "Updating the existing Docker4APEX section..."
    cat ${SQLPLUS_GLOGIN} | sed "s/select upper(sys_context ('userenv', 'con_name') ||.*/select upper(sys_context ('userenv', 'con_name') || \'@${CONTAINER_NAME}\')  global_name from dual;/" > /tmp/glogin.$$
    if [ $? -eq 0 ]
    then
      cat /tmp/glogin.$$ > ${SQLPLUS_GLOGIN}
    else
      echo -e "ERROR: Could not copy for update, the glogin.sql file!"
      exit 1
    fi

    if [ $? -ne 0 ]
    then
      echo -e "ERROR: Could not update the glogin.sql file!"
      exit 2
    fi
  fi
fi
