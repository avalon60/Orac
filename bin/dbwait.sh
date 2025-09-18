
# --- helpers ---------------------------------------------------------------
db_exec() {
  docker exec -i orac-db bash -lc "$*"
}

wait_for_oracle() {
  local dsn='//127.0.0.1:1521/FREEPDB1'
  local tries=${1:-60}   # ~2 minutes
  local delay=2

  echo "⏳ Waiting for Oracle service ${dsn} inside container 'orac-db'..."

  for i in $(seq 1 "$tries"); do
    # Try service login (SYSTEM). Prefer pulling password from env/cred store if you have one.
    if db_exec "sqlplus -L -s system/\"\$ORACLE_PWD\"@${dsn} <<'SQL'
set heading off feedback off pages 0 verify off echo off
select 1 from dual;
exit
SQL
" >/dev/null 2>&1; then
      echo "✅ Oracle service is ready."
      return 0
    fi

    # Fallback: as sysdba, check/open PDB then re-register listener
    db_exec "sqlplus -L -s / as sysdba <<'SQL'
whenever sqlerror exit 1
set heading off feedback off pages 0 verify off echo off
declare
  v_open varchar2(20);
begin
  select open_mode into v_open from v\$pdbs where name = 'FREEPDB1';
  if v_open <> 'READ WRITE' then
    execute immediate 'alter pluggable database freepdb1 open';
    execute immediate 'alter pluggable database freepdb1 save state';
  end if;
end;
/
alter system register;
exit
SQL
" >/dev/null 2>&1

    sleep "$delay"
  done

  echo "❌ Oracle didn’t become ready in time."
  return 1
}
# --------------------------------------------------------------------------

# ... after you (re)start the DB/ORDS container:
# e.g. docker start orac-db  OR  docker compose up -d orac-db
wait_for_oracle 60 || exit 1

# now start Orac AI engine...

