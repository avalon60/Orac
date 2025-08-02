#!/usr/bin/env bash
#
# Author: Clive Bostock
# Script to start the ORDS process.
#

E="-e"
SHORT_VERS=`echo $APEX_VERS | sed "s/\..*//"`
export ORDS_HOME=/home/oracle/ORDS21
echo "Start instigated by 'docker exec' detached process request." | tee -a ${ORDS_HOME}/nohup.out

echo "ORDS_HOME = ${ORDS_HOME}" | tee -a ${ORDS_HOME}/nohup.out
echo "Starting ORDS listener..." | tee -a ${ORDS_HOME}/nohup.out

cd ${ORDS_HOME}
nohup java -Dorg.eclipse.jetty.server.Request.maxFormContentSize=3000000 -jar ords.war &
if [ $? -eq 0 ]
then
 echo "ORDS started OK." | tee -a ${ORDS_HOME}/nohup.out
else
 echo "Error detected starting ORDS server!" | tee -a ${ORDS_HOME}/nohup.out
 exit 1
fi
