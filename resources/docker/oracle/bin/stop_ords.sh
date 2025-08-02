#!/usr/bin/env bash
#
# Author: Clive Bostock
# Script to kill the ORDS process.
#

E="-e"
SHORT_VERS=`echo $APEX_VERS | sed "s/\..*//"`
export ORDS_HOME=/home/oracle/ORDS21
echo $E "ORDS_HOME = ${ORDS_HOME}"

cd ${ORDS_HOME}

ORDS_PID=`ps -ef | grep ords.war | grep -v "grep" | awk '{print($2)}'`
if [ -z "$ORDS_PID" ]
then
  echo "Cannot find a running ORDS process!" 
  exit
fi

kill $ORDS_PID
sleep 2
ORDS_PID=`ps -ef | grep ords.war | grep -v "grep" | awk '{print($2)}'`
if [ -z "$ORDS_PID" ]
then
  echo "ORDS process killed!" 
else
  echo "ORDS process did not die, attempting a kill -9"
  kill -9 $ORDS_PID
fi
ORDS_PID=`ps -ef | grep ords.war | grep -v "grep" | awk '{print($2)}'`
if [ -z "$ORDS_PID" ]
then
  true
else
  echo "Failed to terminate ORDS process ${ORDS_PROC}"
fi
echo Done.
