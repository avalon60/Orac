##!/usr/bin/env bash
#
# Author: Clive Bostock
#   Date: 05 Sep 2021
# Module: app-setup-sql.sh
#
# Relies on the SCRIPTS_DIR variable being set by the calling script.
# This is normally done by the deploy/setup/04-schema-setup.sh script
# which is set to execute when the container is startting up the first
# time.
#
# The script will execute the SQL scripts (.sql extension), found in 
# SCRIPTS_DIR in, alphanumeric order.
#
PROG=`basename $0`

# Setup the env variables for inside the container.
DAPEX_HOME=/var/tmp/dapex
DAPEX_ETC=${DAPEX_HOME}/etc
DAPEX_BIN=${DAPEX_HOME}/bin
DAPEX_SQL=${DAPEX_BIN}/dapex_sql.sh

display_usage()
{
  echo -e "\nUsage: ${PROG} [ -k ] | [ -h ] \n"
  echo -e "   -k preserve (keep) the substitution edits." 
  echo -e "   -h display help"
}

DIRNAME=`echo $0 | sed "s?/${PROG}??"`
ETC=/var/tmp
export SQLPATH=${DIRNAME}:.

unset K
while getopts "hk" options;
do
  case $options in
    h) display_usage; exit;;
    k) K="-k";;
    *) display_usage;
       exit 1;;
   \?) display_usage;
       exit 1;;
  esac
done

cd ${SCRIPTS_DIR}

for SQL_SCRIPT in `ls -1 ${SCRIPTS_DIR}/*.sql | grep -v ebr_demo_tmp.sql` 
do
  SQL_LOG=/var/tmp/dapex/log/`basename ${SQL_SCRIPT} .sql`.log
  $DAPEX_SQL -s ${SQL_SCRIPT} ${K}                            >> ${SQL_LOG} 
done
