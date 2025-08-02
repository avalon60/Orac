#!/usr/bin/env bash
#
# Docker4APEX
#
# 06-update-glogin.sh
#
# Updates the sqlplus glogin.sql file, appending
# Docker4APEX add-on settings as per the
# <DAPEX_HOME>/deploy/etc/glogin.template file.
#
# Set locations within the container...
PROG="80-update-glogin.sh"
DAPEX_BASE=/var/tmp/dapex
DAPEX_BIN=${DAPEX_BASE}/etc
DAPEX_ETC=${DAPEX_BASE}/etc
LOG=${DAPEX_BASE}/log
SQLPLUS_GLOGIN=`find $ORACLE_HOME -name glogin.sql`

# Try get the container name from the container.reg file.
# Failing that we fall back to using the ${ORACLE_SID}.
# Unless something has gone wrong, the last two steps shouldn't be 
# needed.
if [ -f "${DAPEX_ETC}/container.reg" ]
then
  CONTAINER_NAME=`cat ${DAPEX_ETC}/container.reg | grep "^CONTAINER_NAME:" | cut -d":" -f2` 
else
  CONTAINER_NAME=${ORACLE_SID}
fi

if [ -f "${SQLPLUS_GLOGIN}" ]
then
  DAPEX_EDITED=`grep '\-\-\- Docker4APEX' ${SQLPLUS_GLOGIN}`
  if [ -z "${DAPEX_EDITED}" ]
  then
    echo "Updating SQLPlus glogin file at:\n ${SQLPLUS_GLOGIN}"                          | tee -a ${LOG}
    cat ${DAPEX_ETC}/glogin.template | sed "s/%CONTAINER_NAME%/${CONTAINER_NAME}/" >> ${SQLPLUS_GLOGIN}
    echo "Modification complete."
  else
    echo "SQLPlus glogin file already tailored for Docker4APEX at:\n ${SQLPLUS_GLOGIN}"  | tee -a ${LOG}
    echo "No modifcations made."                                                         | tee -a ${LOG}
  fi
fi
echo "${PROG}: Done."                                                                    | tee -a ${LOG}
