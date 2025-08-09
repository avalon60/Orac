# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# Script to configure and install ORDS on container restart
#
PROG='10-start-ords.sh'
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORDS_HOME=${ORAC_HOME}/ords
JAVA_HOME=/usr/lib/jvm/java-17-openjdk
PATH=$JAVA_HOME/bin:$PATH
E="-e"
export ORDS_HOME=${ORAC_HOME}/ords
pushd ${ORDS_HOME}
echo $E "ORDS_HOME = ${ORDS_HOME}" 
CMD="cd ${ORDS_HOME}"
echo "${CMD}"                      
${CMD}
CMD="bin/ords --config /home/oracle/orac/ords/conf serve"
echo ${CMD}                        
nohup ${CMD} &
