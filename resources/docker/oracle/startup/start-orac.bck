#!/bin/bash
set -ex

echo "🔧 Orac container startup initiated..."

# Wait for Oracle DB to be open
echo "⏳ Waiting for DB to accept connections..."
until echo "select open_mode from v\$database;" | sqlplus -s / as sysdba | grep -q "READ WRITE"
do
  echo "🕒 Still waiting for DB..."
  sleep 5
done
echo "✅ Oracle DB is open for business."

# Check APEX install
echo "🔍 Checking for existing APEX installation..."
apex_exists=$(sqlplus -s / as sysdba <<EOF
set heading off feedback off verify off echo off
select count(*) from dba_registry where comp_id = 'APEX';
exit
EOF
)

echo "APEX check result: $apex_exists"

if [[ "$apex_exists" -eq 0 ]]; then
  echo "⚠️ APEX not found. Installing..."
  # Call apexins.sql here
else
  echo "✅ APEX is already installed."
fi

# Keep container alive
echo "✅ Startup complete. Holding container open..."
tail -f /dev/null

