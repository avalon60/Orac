# Author: Clive Bostock
#   Date: 22 Aug 2021
#
# DAPEX script to install APEX on container setup.
#
PROG='030-orac-schema.sh'
E="-e"
echo "${PROG} Started."   
export APEX_HOME=${APEX_HOME:-/home/oracle/orac/setup/apex/apex}
export ORACLE_SID=${ORACLE_SID:-FREE}
export ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
export ORAC_HOME=${ORAC_HOME:-/home/oracle/orac}
export ORACLE_BASE=${ORACLE_BASE:-/opt/oracle}

# Derive the CDN for this release
CDN=" https://static.oracle.com/cdn/apex/${APEX_VERSION}.0/"

pushd ${APEX_HOME}

echo "${PROG} Started"
echo "${PROG} Launching sqlplus; installing APEX..."
sqlplus / as sysdba <<EOF 
alter session set container=${ORACLE_PDB};

create user ORAC identified by ${ORACLE_PWD}
  default tablespace users
  temporary tablespace temp
  quota unlimited on users;

grant create session, create table, create view, create sequence,
      create procedure, create trigger, create type, create synonym
to ORAC;
EOF
echo "${PROG}: Done."     
