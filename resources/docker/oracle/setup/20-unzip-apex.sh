# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# DAPEX script to unzip APEX and ORDS zip files on container setup.
#
PROG='20-unzip-apex.sh'
LOG=`basename $0 .sh`.log
LOG=/var/tmp/dapex/log/${LOG}
if [ "$INC_APEX" = "FALSE" ]
then
  echo "${PROG} APEX install skipped (INC_APEX=${INC_APEX})."                          | tee -a ${LOG}
else
  echo "${PROG} Started."                                                              | tee -a ${LOG}
  APEX_FILE=apex_${APEX_VERS}.zip
  echo "Unzipping $APEX_FILE"                                                          | tee -a ${LOG}
  unzip -o $ORACLE_BASE/scripts/setup/$APEX_FILE -d /home/oracle/${ORACLE_PDB}         | tee -a ${LOG}
  unzip -o $ORACLE_BASE/scripts/setup/ords-21.2.0.174.1826.zip -d /home/oracle/ORDS21  | tee -a ${LOG}
fi
