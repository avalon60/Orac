# Author: Clive Bostock
#   Date: 24 Apr 2026
#
# Orac script to create the ORAC_PLUGIN schema user on container setup.
#
E="-e"
PROG="Orac: 031-orac-plugin-user.sh"
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
echo "[$(timestamp)] ${PROG} Started"
export APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
export ORACLE_SID=${ORACLE_SID:-FREE}
export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}

pushd ${APEX_HOME}

echo "${PROG} Started"
echo "${PROG} Launching sqlplus; creating ORAC_PLUGIN..."
sqlplus / as sysdba <<EOF
alter session set container=${ORACLE_PDB};

create user ORAC_PLUGIN identified by ${ORACLE_PWD}
  default tablespace users
  temporary tablespace temp
  quota unlimited on users;

grant create session, create table, create view, create sequence,
      create procedure, create trigger, create type, create synonym
to ORAC_PLUGIN;

EOF
echo "[$(timestamp)] ${PROG}: Done."
