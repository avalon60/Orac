# APEX Standards

## Purpose

This document defines standards for Oracle APEX workspace and application
exports that are delivered as database assets in Orac.

These standards apply to files under:

- `resources/db/apex/orac_ws/`
- `resources/db/apex/orac_apps/`
- plugin-supplied APEX exports under `plugins/<plugin-code>/apex/`

APEX exports are database-delivered application assets. They are not web
application source files and must not be moved into the `web` tree.

## Core Rules

- Preserve the shared Orac workspace and parsing-schema model documented in
  `resources/db/schema/AGENT_CONTEXT.md`.
- Keep Orac-owned APEX exports under `resources/db/apex`; do not place them
  under schema-owned Liquibase controller trees.
- Do not grant APEX applications direct access to `orac_core` tables.
- Use approved `orac_code` views and packages for APEX-facing data access.
- Preserve APEX authentication, authorization, and session behaviour unless the
  change explicitly requires a reviewed security update.
- Do not expose secrets, raw credentials, bearer tokens, or unredacted plugin
  error values through APEX regions, card bodies, links, reports, or logs.

## Application IDs

- Orac internal APEX applications should use application IDs greater than or
  equal to `1042`.
- Plugin-supplied APEX applications should use application IDs greater than or
  equal to `10010`.
- Before adding or changing an APEX application ID, check both
  `resources/db/apex/orac_apps/` and plugin manifests that declare APEX
  applications to avoid ID collisions.

## Maintenance Dialog Actions

Maintenance dialogs are APEX modal pages used to create, update, or administer
one persisted row or configuration object.

- Include visible `Cancel` and `Save` actions by default.
- `Cancel` must not validate page items and must not run create, update, or
  delete processes.
- `Save` must submit through the reviewed application API/package path and must
  run only the intended save process.
- Successful modal maintenance actions must close the dialog with the APEX
  close-dialog process pattern, normally `NATIVE_CLOSE_WINDOW`, and refresh the
  parent report or region on `apexafterclosedialog`. Do not redirect a full page
  from inside the modal after `Save` or `Delete`.
- When the request does not specify deletion behaviour, ask whether a `Delete`
  action is required. Include a recommendation: omit deletion, allow deletion,
  or make deletion conditional, based on data history, audit, and referential
  risk.
- When `Delete` is included, make it visible only where deletion is meaningful,
  normally existing rows. It must be confirmation-protected, danger-styled,
  skip validation, and run only the intended delete process.
- APEX maintenance dialogs must not use direct table DML or automatic row
  processing against protected owner tables unless that is the explicit,
  reviewed design for the page.
- When generating or manually editing maintenance dialogs, add or update static
  item-reference integrity checks. Page processes, dynamic actions, branches,
  validations, item-submit lists, URLs, and JavaScript must not reference page
  items that are not defined in the current export.
- When a page item is removed or renamed, remove or update every related
  process, dynamic action, branch, validation, item-submit list, URL, and
  JavaScript reference in the same change.

## Card Standards

Hub-style APEX card pages in application `1042`, and launcher pages that need
to match them, must use the same visual card style as the existing `Orac Admin`,
`Model Admin`, and `Plugins` hubs.

The required visual contract is:

- featured icon band at the top of each card
- circular icon treatment using Font APEX icons
- centered title and subtitle/header text
- separated body text area beneath the header
- three-column desktop layout
- consistent card width and inter-card spacing
- Universal Theme colour cycling or an explicitly equivalent scoped colour rule
- full-card navigation where the card is an entry point

For list-backed card hubs, use:

- `NATIVE_LIST`
- list template `2886769488667748277`
- card region template `4501440665235496320`
- component template options containing:
  - `u-colors`
  - `t-Cards--featured`
  - `t-Cards--block`
  - `force-fa-lg`
  - `t-Cards--displayIcons`
  - `t-Cards--3cols`
  - `t-Cards--animColorFill`

Do not replace these list-backed hub cards with native Cards unless the page
needs SQL-driven rows or dynamic link preparation that cannot be represented by
an APEX list.

Cards should include:

- a clear title
- a Font APEX icon class
- short descriptive body text where the card is not self-explanatory
- a direct, intentional link target

SQL-driven `NATIVE_CARDS` listings must preserve equivalent behaviour. Use
native Cards only when the data source must remain query-backed, such as plugin
application launchers sourced from approved registry views.

Required native Cards settings:

- `p_plug_source_type=>'NATIVE_CARDS'`
- `p_plug_template=>4501440665235496320`
- `p_layout_type=>'GRID'`
- `p_grid_column_count=>3`
- dynamic icon class source, normally `p_icon_source_type=>'DYNAMIC_CLASS'`
- top icon placement, normally `p_icon_position=>'TOP'`
- full-card action with an intentional link target
- title, subtitle, body, and icon values sourced from approved views
- no direct reads from protected owner tables

Because native Cards do not render the `NATIVE_LIST` card template options in
the same way, SQL-driven card hubs that are expected to match the `1042` hub
cards must also define scoped CSS hooks and sizing rules.

For the plugin application launcher pattern, use:

- region CSS class `orac-plugin-card-hub`
- native Cards component CSS class `orac-plugin-card-hub`
- native Cards card CSS class `orac-plugin-card`
- grid tracks sized to the standard hub card width, currently `26.25rem`
- a maximum grid width for three desktop columns, currently `80.75rem`
- an inter-card gap of `1rem`
- responsive behaviour that collapses to fewer columns without horizontal
  overflow
- scoped icon-band colour cycling, including a distinct second-card colour

Avoid fixed narrow card widths inside APEX-generated three-column grid tracks;
that creates large visual gaps between cards and no longer matches the 1042 hub
display.

## Plugin APEX Applications

Plugin-supplied APEX applications must be installed into the shared Orac
workspace and listed through the approved plugin APEX app registry path.

New plugin APEX applications should be derived from the maintained scaffold:

```text
resources/db/apex/orac_apps/f10042.sql
```

Scaffold-derived apps must preserve the cross-app return navigation application
items, application-level `BEFORE_HEADER` preparation process, Page 0 return
region, and `ORAC_THEME_SYNC` behaviour unless a reviewed change explicitly
replaces them. Do not recreate return navigation with browser-side stack
parsing, raw return URLs, or plugin-owned navigation logic.

Scaffold-derived apps should preserve the approved plugin card styling pattern
for launcher or entry cards. If a plugin app needs a different page pattern,
document why the standard scaffold cards are not suitable and keep full-card
navigation, Font APEX icons, and responsive Universal Theme layout conventions
where applicable.

Listing pages must hide disabled, failed, and metadata-only plugin app rows.
Dynamic plugin app card links must be prepared by the approved view or package
path and must not be assembled from raw user input in the APEX export.

Plugin APEX applications launched from application `1042` should honour the
`ORAC_THEME_SYNC` request marker. When present, the launched application should
match the current `1042` Universal Theme style by style name, and must fail
closed without changing behaviour if the matching style is unavailable.

## Auto-maintained columns
Typically Orac tables include the following columns:
These are the Orac standard, trigger maintained columns.
created_on      -- Orac local row-created timestamp
updated_on      -- Orac local row-updated timestamp
row_version     -- Orac local optimistic-lock/audit helper

These are trigger maintainded, and must not be updated by APEX apps. Unless explicitly requested, they are not included in APEX applications.
