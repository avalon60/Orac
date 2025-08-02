#!/usr/bin/env bash
#
# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# DAPEX checks for a ps1.txt file. If it exists it is appended to ~oracle/.bashrc
#
PROG=`basename $0 .sh`
DAPEX_HOME=/var/tmp/dapex
DAPEX_ETC=${DAPEX_HOME}/etc
DAPEX_BIN=${DAPEX_HOME}/bin
LOGIN_TEMPLATE="${DAPEX_ETC}/login.template"
E="-e"
LOG=`basename $0 .sh`.log
LOGBASE=/var/tmp/dapex/log/${LOG}

append_bashrc ()
{
  echo -e "Setting login tweaks (PS1) etc for oracle"
  cat ${LOGIN_TEMPLATE} | sed "s/%ORACLE_PDB%/${ORACLE_PDB}/"      >> /home/oracle/.bashrc
}

remove_old_lines()
{
  START_LINE=`sed -n "/DO NOT EDIT THIS Docker4APEX SECTION./=" /home/oracle/.bashrc`
  END_LINE=`sed -n "/End Docker4APEX settings/="                /home/oracle/.bashrc`
  if [ ! -z "${START_LINE}" ] && [ ! -z "${END_LINE}" ]
  then
    sed "${START_LINE},${END_LINE}d" /home/oracle/.bashrc     > /tmp/bashrc.$$ 
    mv /tmp/bashrc.$$ /home/oracle/.bashrc
  fi
}

update_bashrc ()
{
  PS1_LINE=`sed -n "/PS1=/=" /home/oracle/.bashrc`
  START_LINE=`sed -n "/DO NOT EDIT THIS Docker4APEX SECTION./=" /home/oracle/.bashrc`
  END_LINE=`sed -n "/End Docker4APEX settings/="                /home/oracle/.bashrc`
  if [ ! -z "${START_LINE}" ] && [ ! -z "${END_LINE}" ] 
  then
                                        #########################################
                                        #  We already have a formal Docker4APEX 
                                        # comment block. remove it and add the  
                                        # latest version.                       
                                        #########################################
    remove_old_lines
    cat ${LOGIN_TEMPLATE} | sed "s/%ORACLE_PDB%/${ORACLE_PDB}/"    >> /home/oracle/.bashrc
    return
  elif [ -z "${PS1_LINE}" ] 
  then
                                        #########################################
                                        #  So no PS1 assignment and no previous 
                                        # Docker4APEX comment block.            
                                        #########################################
    append_bashrc
    return
  fi
                                        #########################################
                                        #  If we get to this point, we have a   
                                        # PS1 assignment already, but not within
                                        # a formal comment block. Maybe this is 
                                        # based on a snapshot image, which pr-  
                                        # dates the introduction of the format  
                                        # comment block.                        
                                        #########################################
  echo -e "Updating PS1 prompt for the oracle account."
                                        #########################################
                                        #  Comment out the offending PS1 line,
                                        # and formalise a block with a PS1 entry.   
                                        #########################################
  cat /home/oracle/.bashrc | sed "s/^PS1=/# &/"      >  /tmp/bashrc.$$
  cp /tmp/bashrc.$$                                     /home/oracle/.bashrc
  append_bashrc
}

UPDATE=N
if [ "$1" = "force" ]
then
  FORCE=Y
fi

PS1_CHK=`cat /home/oracle/.bashrc | grep -v "^ *#" | grep "PS1="` 
if [ ! -z "${PS1_CHK}" ] && [ "${FORCE}" != "Y" ]
then
  echo "PS1 prompt already set in /home/orcle/.bashrc - no action taken."
  exit;
elif [ "${FORCE}" = "Y" ]
then
  UPDATE=Y
else
  UPDATE=N
fi

echo "${PROG} Started."

if [ "${FORCE}" = "Y" ]
then
  echo "${PROG} running in assertive mode."
fi

if [ -f "${LOGIN_TEMPLATE}" ]
then
  if [ "${UPDATE}" = "Y" ]
  then
    update_bashrc
  else
    append_bashrc
  fi
  STATUS=$?
  if [ ${STATUS} -ne 0 ]
  then
    echo "Error ${STATUS} encountered whilst updating .bashrc file for oracle." 
  fi
  
else
  echo -e "No action taken."
  echo -e "Supplemental: Login snippet file not found: ${LOGIN_TEMPLATE}"
fi
