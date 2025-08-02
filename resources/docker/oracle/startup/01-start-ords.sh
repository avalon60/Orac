# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# Script to configure and install ORDS on container restart
#
PROG='10-start-ords.sh'
LOG=`basename $0 .sh`.log
LOG=/var/tmp/dapex/log/${LOG}
E="-e"
if [ "$INC_APEX" = "FALSE" ]
then
  echo "${PROG} APEX start ORDS skipped - APEX/ORDS not installed here (INC_APEX=${INC_APEX})."                        | tee -a ${LOG}
  exit
fi
SHORT_VERS=`echo $APEX_VERS | sed "s/\..*//"`
export ORDS_HOME=/home/oracle/ORDS21
echo $E "ORDS_HOME = ${ORDS_HOME}" | tee -a ${LOG}
CMD="cd ${ORDS_HOME}"
echo "${CMD}"                      | tee -a ${LOG}
${CMD}
CMD="nohup java -Dorg.eclipse.jetty.server.Request.maxFormContentSize=3000000 -jar ords.war &"
echo ${CMD}                        | tee -a ${LOG}
nohup java -Dorg.eclipse.jetty.server.Request.maxFormContentSize=3000000 -jar ords.war &
