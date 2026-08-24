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
usage privilege history. Its manage action passes only the numeric privilege
row ID to Page 40. Scope type and target are displayed separately; no
concatenated canonical scope is used as a report value or form protocol.

For a new grant, Page 40 presents scope type separately from a conditional
Project or Plugin selector. Each selector returns a `knowledge_scope_id`. For
an existing entry, principal, scope type, target, effective date, and expiry
date are read-only. Revoke targets that exact row by ID and protected row
version, sets its stored active state to `N`, and records the revocation actor,
reason, and timestamp. The row remains visible as revoked history and becomes
view-only; re-granting creates a new history row. Project and Plugin filters
and form targets are mutually exclusive and are shown declaratively from Scope
Type. Page 40 calls
`orac_code.rag_usage_privilege_api` and performs no direct table DML. APEX is
an administration surface, not an independent authorization authority.

In new-grant mode, changes to Principal, Scope Type, Project, or Plugin invoke
the package's read-only lifecycle check. If an unexpired stored-active grant
already reserves that principal/target relationship, Page 40 displays `An
applicable grant already exists for this principal and target.` and disables
Grant. Clearing or changing the selection hides the message and enables the
button again. The same package check runs as a Grant-only server validation,
and the grant process converts a race-time `RAG_USAGE_ALREADY_GRANTED` result
to the same clear inline error rather than reporting a no-op as success.

## Document Ingestion Administration

Document ingestion configuration spans three APEX applications with distinct
owners:

| Application | Relevant pages | Responsibility |
| --- | --- | --- |
| Orac Administration, App 1042 | 37/38 | Register, edit, activate, or deactivate project targets. |
| Orac Administration, App 1042 | 39/40 | Grant or revoke authenticated-user retrieval access to canonical project/plugin scopes. |
| Plugin Control, App 1043 | 1 | Inspect managed service state and set the Drop Box scanner policy to `auto`, `manual`, or `disabled`. |
| Plugin Control, App 1043 | 2 | Launch enabled installed plugin applications. |
| Plugin Control, App 1043 | 3/4 | Inspect and change plugin APEX-app enablement. |
| Drop Box Admin, App 10020 | 1-5 | Configure watched locations and inspect Drop Box/Core ingestion activity. |

Register and activate a project on Pages 37/38 before selecting it as a Drop
Box project target. Plugin targets come from the installed, enabled, eligible
plugin registry.

Pages 39/40 control dialogue retrieval permission. A RAG usage grant does not
create a scope, enable ingestion, or authorise a Drop Box submission.
Classification tags are Core-owned, but there is currently no tag-maintenance
page in App 1042; App 10020 selects active tags through the approved Core LOV.

The same `USE` grant authorises the Core runtime's bounded normalised-content
retrieval API. App 1042 administers and reports privileges only: neither
`ORAC_APX_PUB` nor any APEX application receives document bytes, artefact
descriptors, the content-bearing chunk view, managed-store keys, or filesystem
access. A future download UI requires a separate reviewed design.

The Core `orac_core` / `knowledge_ingestion` worker appears in managed service
status only when `[knowledge].enabled` permits registration. App 1043 does not
edit Core chunking, embedding, managed-storage, or dialogue-retrieval settings.

See [Document Ingestion](document-ingestion.md) for the complete Core
configuration and ownership model and the
[Drop Box operator guide](../plugins/drop_box/docs/drop-box.md) for every
App 10020 field and lifecycle report.

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
