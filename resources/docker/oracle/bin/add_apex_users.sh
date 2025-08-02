#!/usr/bin/env bash
#
# Docker4APEX
#
# add_apex_users.sh:
#
# Creates APEX developer accounts based on the contents
# of an apex_users.dat file. The record in the file should
# be colon delimited as:
#
#   Username:Email-Id:Default-Schema:APEX-Workspace
#
#
PROG=`basename $0`
DAPEX_SQL=/var/tmp/dapex/bin/dapex_sql.sh
LOGPATH=/var/tmp/dapex/log/`basename $0 .sh`.log

display_usage()
{
  echo -e "\nUsage: ${PROG} -u apex_users.dat | -h \n"
  echo -e "   -u apaex_users.dat file.\n" 
  echo -e "   -h Display help.\n" 
}

while getopts "hu:" options;
do
  case $options in
    h) display_usage; exit;;
    u) USERS_FILE=${OPTARG};;
    *) display_usage;
       exit 1;;
   \?) display_usage;
       exit 1;;
  esac
done

if [ -z "${USERS_FILE}" ]
then
    echo "${PROG}: You must specify an add apex users file!"
    display_usage
    exit 1
fi

LINE_NO=0
while IFS= read -r line
do
  let LINE_NO=$LINE_NO+1
   ## take some action on $line
  USERNAME=`echo $line       | cut -d"|" -f1`
  if [ -z "$USERNAME" ]
  then
    echo -e "WARNING: Username, extracted as empty string, from line ${LINE_NO}, of ${USERS_FILE}"
    echo -e "This row will be ignored!"
    continue
  fi
  FIRST_NAME=`echo $line       | cut -d"|" -f2`
  LAST_NAME=`echo $line       | cut -d"|" -f2`

  EMAIL_ID=`echo $line       | cut -d"|" -f4`
  if [ -z "$EMAIL_ID" ]
  then
    echo -e "WARNING: Email Id, extracted as empty string, from line ${LINE_NO}, of ${USERS_FILE}!"
    echo -e "Setting a dummy email id as: ${USERNAME}@nowhere.com"
    EMAIL_ID="${USERNAME}@nowhere.com"
  fi

  DEFAULT_SCHEMA=`echo $line | cut -d"|" -f5`
  if [ -z "$DEFAULT_SCHEMA" ]
  then
    echo -e "WARNING: Email Id, extracted as empty string, from line ${LINE_NO}, of ${USERS_FILE}!"
    echo -e "This row will be ignored!"
    continue
  fi

  APEX_WORKSPACE=`echo $line | cut -d"|" -f6`
  if [ -z "$APEX_WORKSPACE" ]
  then
    echo -e "WARNING: Workspace, extracted as empty string, from line ${LINE_NO}, of ${USERS_FILE}!"
    echo -e "This row will be ignored!"
    continue
  fi

  APEX_PRIVILEGES=`echo $line | cut -d"|" -f7`

  cat /var/tmp/dapex/etc/add_apex_user.sql | sed "s/%USERNAME%/${USERNAME}/g"                | 
                                             sed "s/%FIRST_NAME%/${FIRST_NAME}/g"            |  
                                             sed "s/%LAST_NAME%/${LAST_NAME}/g"              |  
                                             sed "s/%EMAIL_ID%/${EMAIL_ID}/g"                |  
                                             sed "s/%DEFAULT_SCHEMA%/${DEFAULT_SCHEMA}/g"    |  
                                             sed "s/%APEX_WORKSPACE%/${APEX_WORKSPACE}/g"    |
                                             sed "s/%APEX_PRIVILEGES%/${APEX_PRIVILEGES}/g"  > /tmp/add_apex_user.sql

  echo -e "Adding APEX user account ${USERNAME} to workspace ${APEX_WORKSPACE}." >> ${LOGPATH}
  if [ -z "$APEX_PRIVILEGES" ]
  then
    PRIVS="Runtime only"
  else
    PRIVS= `echo ${APEX_PRIVILEGES} | sed "s/:/, /g"`
  fi
  echo -e "...        Email id: ${EMAIL_ID}"                                          >> ${LOGPATH}
  echo -e "...  Default schema: ${EMAIL_ID}"                                          >> ${LOGPATH}
  echo -e "...  APEX workspace: ${APEX_WORKSPACE}"                                    >> ${LOGPATH}
  echo -e "...      Privileges: ${PRIVS}"                                             >> ${LOGPATH}
  $DAPEX_SQL -s /tmp/add_apex_user.sql

done <<<"$(cat ${USERS_FILE} | grep -v "^#")"
