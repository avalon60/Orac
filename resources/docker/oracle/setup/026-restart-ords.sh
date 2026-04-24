#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 15 Mar 2026
#
# Orac script to restart ORDS as part of post install steps
#
# 026-restart-ords.sh
set -Eeuo pipefail

ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
ORDS_HOME=${ORAC_HOME}/ords
ORDS_CONF=${ORDS_HOME}/conf
JAVA_HOME=/usr/lib/jvm/java-17-openjdk
PATH=$JAVA_HOME/bin:$PATH

pkill -f ords || true

cd "${ORDS_HOME}"
nohup ./bin/ords --config "${ORDS_CONF}" serve >/tmp/ords-restart.log 2>&1 &
