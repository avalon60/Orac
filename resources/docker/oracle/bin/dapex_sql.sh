#!/usr/bin/env bash
#
# dapex_sql.sh - prepares and executes a sql file
#
#                Preparation involves on the fly substitution of
#                %variable% format variables for their shell 
#                counterparts.
#
PROG=`basename $0`
LOGNAME=`basename $0 .sh`

display_usage()
{
  echo -e "\nUsage: ${PROG} -s script_name [ -k ] | -h \n"
  echo -e "   -s script_name. Executes sql_script_name.\n" 
  echo -e "   -k preserve (keep) the substitution edits." 
  echo -e "   WARNING: Only use this option for debuggng." 
  echo -e "            Scripts called multiple times,"
  echo -e "            may result in unpredicable results." 
}

# edit_script: Edits the sql script to replace substitution 
# placeholders with shell variable counterparts. This means
# we don't have to pass varied parameters, for different
# scripts.
edit_script ()
{
  cat $1 | sed "s/%ORACLE_PWD%/${ORACLE_PWD}/g"   \
         | sed "s/%ORACLE_PDB%/${ORACLE_PDB}/g"   \
         | sed "s/%ORACLE_SID%/${ORACLE_SID}/g"   > dapex_tmp.sql
}

SCRIPT_NAME=$1

while getopts "hks:" options;
do
  case $options in
    h) display_usage; exit;;
    s) SCRIPT_NAME=${OPTARG};;
    k) KEEP_EDIT=Y;;
    *) display_usage;
       exit 1;;
   \?) display_usage;
       exit 1;;
  esac
done

echo "${PROG} Editng and running script: ${SCRIPT_NAME}" >> /var/tmp/dapex/log/${LOGNAME}.log
# Edit the script to replace substitution placeholders with shell variable counterparts.
edit_script ${SCRIPT_NAME}

if [ "${KEEP_EDIT}" = "Y" ]
then
  echo "Keep edit for script ${SCRIPT_NAME} requested."  >> /var/tmp/dapex/log/${LOGNAME}.log
  echo "Current directory: `pwd`"                        >> /var/tmp/dapex/log/${LOGNAME}.log
  echo "cp dapex_tmp.sql ${SCRIPT_NAME}"                 >> /var/tmp/dapex/log/${LOGNAME}.log
  cp dapex_tmp.sql ${SCRIPT_NAME}
else
  echo "${SCRIPT_NAME} will be purged."                  >> /var/tmp/dapex/log/${LOGNAME}.log
fi

sqlplus / as sysdba @dapex_tmp.sql

rm dapex_tmp.sql
echo "${PROG} Done." >> /var/tmp/dapex/log/${LOGNAME}.log
