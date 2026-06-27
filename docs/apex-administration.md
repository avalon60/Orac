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

## User Preference Sliders

The administration preference editor renders slider-capable numeric
preferences from catalogue metadata. Page 6 uses a native metadata-driven range
input created with DOM APIs inside the fixed `ORAC_PREF_SLIDER_HOST` region.
The submitted APEX item is hidden and carries only the selected value.

The FOS Range Slider plug-in is already present in the exported application and
is kept as a vendored optional APEX plug-in. Native Page 6 slider rendering does
not use FOS because the vendored plug-in's min, max, and step settings are
static APEX component attributes rather than row-specific preference metadata.
It does not require a separate `com_fos_range_slider.sql` deployment step.

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
