# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# Script to cleanup, removing the ORDS and APEX zip files after
# installation.
#
E="-e"
PROG="50-clean-up-files.sh"
LOG=`basename $0 .sh`.log
LOG=/var/tmp/dapex/log/${LOG}

echo "${PROG} Started."                 | tee -a ${LOG}
echo "Cleaning up APEX tmp files..."    | tee -a ${LOG}
cd $ORACLE_BASE/scripts/setup
echo "Removing:"                        | tee -a ${LOG}
ls apex*.zip ords*.zip                  | tee -a ${LOG}
rm -r apex*.zip ords*.zip               | tee -a ${LOG}
echo "${PROG}: Done."                   | tee -a ${LOG}
