# APEX Administration

Orac's browser-based administration application is delivered through Oracle
APEX and ORDS in the local database container.

## Open the Application

After the stack is running, open:

```text
http://localhost:8042/ords/r/orac/orac-administration1042/login
```

For remote access, replace `localhost` with the Orac host name or IP address.

| Setting | Value |
|---|---|
| Workspace | `ORAC` |
| Initial application user | `ORAC_ADMIN` |
| Password | Set through the deployed application's account process |

The APEX developer workspace is separate from the Orac administration
application:

```text
http://localhost:8042/ords/r/apex/workspace-sign-in/oracle-apex-sign-in
```

## Troubleshooting

1. Confirm the stack and database are running:

   ```bash
   bin/orac-ctl.sh status
   bin/orac-ctl.sh logs db
   ```

2. Confirm the configured host port maps to container port `8080`.

3. Confirm the application URL contains `/ords/r/orac/orac-administration1042/login`.

4. Use a private browser window to rule out stale APEX/ORDS sessions.

5. Confirm APEX is installed from an administrative database session:

   ```sql
   SELECT version FROM apex_release;
   ```

Do not grant broad database privileges or alter application/schema ownership to
work around login failures. Diagnose ORDS, APEX workspace, account, and port
configuration separately.
