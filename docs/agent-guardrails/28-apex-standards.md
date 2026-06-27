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

## Card Standards

Hub-style APEX card pages in application `1042` must use the same visual card
style as the existing `Orac Admin` and `Model Admin` hubs.

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

Cards should include:

- a clear title
- a Font APEX icon class
- short descriptive body text where the card is not self-explanatory
- a direct, intentional link target

SQL-driven `NATIVE_CARDS` listings should preserve equivalent behaviour:

- three-column grid layout
- icon-led display
- the `1042` hub-card component options where the native component supports
  them
- full-card link action
- title, subtitle, body, and icon values sourced from approved views
- no direct reads from protected owner tables

## Plugin APEX Applications

Plugin-supplied APEX applications must be installed into the shared Orac
workspace and listed through the approved plugin APEX app registry path.

Listing pages must hide disabled, failed, and metadata-only plugin app rows.
Dynamic plugin app card links must be prepared by the approved view or package
path and must not be assembled from raw user input in the APEX export.

Plugin APEX applications launched from application `1042` should honour the
`ORAC_THEME_SYNC` request marker. When present, the launched application should
match the current `1042` Universal Theme style by style name, and must fail
closed without changing behaviour if the matching style is unavailable.
