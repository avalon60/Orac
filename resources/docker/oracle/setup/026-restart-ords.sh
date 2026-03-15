#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 15 Mar 2026
#
# Orac script to restart ORDS as part of post install steps
#
# 026-restart-ords.sh
pkill -f ords
./bin/ords --config ${ORDS_CONF} serve &
