# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# DAPEX script to configure and install ORDS on container setup
#
E="-e"
PROG='40-setup-ords.sh'
LOG=`basename $0 .sh`.log
LOG=/var/tmp/dapex/log/${LOG}

if [ "$INC_APEX" = "FALSE" ]
then
  echo "${PROG} APEX install skipped (INC_APEX=${INC_APEX})."                        | tee -a ${LOG}
else
  echo "${PROG} Started."            | tee -a ${LOG}
  
  cd ${ORACLE_BASE}/scripts/setup
  SHORT_VERS=`echo $APEX_VERS | sed "s/\..*//"`
  export ORDS_HOME=/home/oracle/ORDS21
  export APEX_HOME=/home/oracle/${ORACLE_PDB}/apex
  echo $E "ORDS_HOME = ${ORDS_HOME}" | tee -a ${LOG}
  echo $E "APEX_HOME = ${APEX_HOME}" | tee -a ${LOG}
  cat ords_params.properties | sed "s/%APEX_VER%/${ORACLE_PDB}/" | sed "s/%ORACLE_SID%/$ORACLE_SID/g"  \
       | sed "s/%ORACLE_PWD%/$ORACLE_PWD/g" > ${ORDS_HOME}/params/ords_params_${ORACLE_SID}.properties
  
  cd $ORDS_HOME
  rm nohup.out 2> /dev/null
  if [ -d "${ORDS_HOME}/conf" ]
  then
    rm -fr ${ORDS_HOME}/conf
  fi
  
  echo -e "Setting the ORDS config directory..."             | tee -a ${LOG}
  CMD="java -jar ords.war configdir ${ORDS_HOME}/conf"
  echo ${CMD}
  ${CMD}
  echo -e "Starting ORDS listener..."                        | tee -a ${LOG}
  CMD="nohup java -jar ords.war install --parameterFile  ${ORDS_HOME}/params/ords_params_${ORACLE_SID}.properties --silent &"
  echo ${CMD} | tee -a ${LOG}
  echo "Parameter File: ${ORDS_HOME}/params/ords_params_${ORACLE_SID}.properties" | tee -a ${LOG}
  echo "====================================================================================================================" | tee -a ${LOG}
  cat ${ORDS_HOME}/params/ords_params_${ORACLE_SID}.properties | tee -a ${LOG}
  echo "====================================================================================================================" | tee -a ${LOG}
  nohup java -jar ords.war install --parameterFile  ${ORDS_HOME}/params/ords_params_${ORACLE_SID}.properties --silent &
fi
echo "${PROG}: Done."                                      | tee -a ${LOG}
