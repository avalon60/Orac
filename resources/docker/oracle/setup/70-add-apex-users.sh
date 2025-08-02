# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# DAPEX checks for request, and if required sets up APEX user accounts.
#
PROG="70-add-apex-users.sh"
DAPEX_HOME=/var/tmp/dapex
DAPEX_ETC=${DAPEX_HOME}/etc
DAPEX_BIN=${DAPEX_HOME}/bin
ADD_APEX_USERS=${DAPEX_BIN}/add_apex_users.sh
E="-e"

LOG=`basename $0 .sh`.log
LOGBASE=/var/tmp/dapex/log/${LOG}
echo "${PROG} Started."                                                              | tee -a ${LOG}

if [ -z "${APP_SCHEMA}" ] &&  [ ! -z "${APEX_ACCOUNTS_FILE}" ]
then
  echo -e "No application schema has been setup - skipping any APEX accounts setup." | tee -a ${LOG}
elif [ ! -z "${APEX_ACCOUNTS_FILE}" ]
then
  echo -e "Proceeding with APEX accounts setup, from file: ${APEX_ACCOUNTS_FILE}"    | tee -a ${LOG}
  ${ADD_APEX_USERS} -u ${DAPEX_ETC}/${APEX_ACCOUNTS_FILE}                            | tee -a ${LOG}
fi
echo "${PROG}: Done."                                                                | tee -a ${LOG}
