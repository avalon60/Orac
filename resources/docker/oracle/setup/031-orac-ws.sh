#!/usr/bin/env bash
# Author: Clive Bostock
#   Date: 9 Aug 2025
#
# Orac script to configure Orac/APEX workspace on container setup.
#
# 031-orac-ws.sh
(
  set -Eeuo pipefail
  sqlplus / as sysdba @/home/oracle/orac/setup/apex/install_workspace.sql
)
