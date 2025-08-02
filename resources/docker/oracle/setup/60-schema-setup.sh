# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# DAPEX script to install required schemas.
#
E="-e"
PROG="60-schema-setup.sh"
LOG=`basename $0 .sh`.log
LOGBASE=/var/tmp/dapex/log/${LOG}
echo "${PROG} Started."                                     | tee -a ${LOG}

if [ -z "${APP_SCHEMA}" ]
then
  echo -e "No schemas setup required."                      | tee -a ${LOG}
else
  for SCHEMA in ${APP_SCHEMA}
  do
    if [ -x "/var/tmp/dapex/schemas/${SCHEMA}/${SCHEMA}_setup.sh" ]
    then
      echo -e "Executing setup.sh for schema ${SCHEMA}..."    | tee -a ${LOG}
      export SCRIPTS_DIR=/var/tmp/dapex/schemas/${SCHEMA}   
      /var/tmp/dapex/schemas/${SCHEMA}/${SCHEMA}_setup.sh     | tee -a ${LOG}
    fi
  done
fi
echo "${PROG}: Done."                                       | tee -a ${LOG}
