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

## RAG Usage Privileges

Application 1042 Page 39 reports active, scheduled, expired, and revoked RAG
usage privilege history. Page 40 selects active principals and eligible
canonical scopes and calls `orac_code.rag_usage_privilege_api`; it performs no
direct table DML. APEX is an administration surface, not an independent
authorization authority.

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

## Cross-App Return Navigation

Orac-managed APEX applications use a validated session-state return stack for
cross-application navigation. The stack is rendered through a Page 0 header
list region named `Cross-App Return Navigation`.

The Universal Theme Navigation Bar list template renders a parent entry with
child entries as a menu button, not as a direct link. Keep the immediate return
destination as a separate primary list entry, and put deeper return targets
under an adjacent compact menu entry. Return labels and URLs must continue to
come from `orac_code.apex_return_nav_api`; do not construct return URLs in the
APEX export or browser-side JavaScript.

## Plugin App Scaffold

New plugin APEX applications should start from the maintained scaffold export:

```text
resources/db/apex/orac_apps/f10042.sql
```

The scaffold includes the approved cross-app return navigation items, Page 0
return control, application-level return preparation process, theme sync
process, and standard plugin card styling. When deriving a real plugin app,
change the application id, alias, name, card content, and manifest `apex_apps`
metadata, but preserve the navigation and security patterns unless the change
has been explicitly reviewed.

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
