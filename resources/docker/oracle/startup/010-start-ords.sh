# Author: Clive Bostock
#   Date: 22 Nov 2025
#
# Script to configure and install ORDS on container restart
#
PROG='10-start-ords.sh'
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORDS_HOME=${ORAC_HOME}/ords
export ORDS_CONF=${ORDS_HOME}/conf
JAVA_HOME=/usr/lib/jvm/java-17-openjdk
PATH=$JAVA_HOME/bin:$PATH
pushd "${ORDS_HOME}" >/dev/null
echo "-e ORDS_HOME = ${ORDS_HOME}"
echo "./bin/ords --config ${ORDS_CONF} serve"
nohup ./bin/ords --config "${ORDS_CONF}" serve >/tmp/ords-start.log 2>&1 &
popd >/dev/null
