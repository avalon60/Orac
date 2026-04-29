# Preference LOV Metadata Refactor Plan

## Purpose

Move Orac user-preference LOV handling from the current partially
metadata-driven model to a fully metadata-driven model.

The immediate goal is to stop needing one-off code and APEX patches for
normal scalar LOV preferences such as `timezone`,
while preserving the current search-backed `weather_location` flow.

The long-term goal is:

- adding a new LOV-backed preference should usually be a data change
- APEX page 6 should stay generic
- LOV execution should remain governed and safe

## Current State

The `orac_core.preference_definitions` table now stores:

- `pref_key`
- `value_type`
- `control_type`
- `lov_type`
- `lov_query`
- `static_lov_code`
- validation/display metadata

However, the runtime path is still only partially metadata-driven.

Current behaviour:

- page 6 reads `control_type` and `value_type` from metadata
- page 6 chooses which item family to show based on that metadata
- LOV rows are still resolved through `orac_code.preference_lov_api`
- `preference_lov_api` contains hard-coded branches for known keys

That means:

- the metadata table is authoritative for structure
- but not yet authoritative for LOV execution

## Problem Statement

The current design still requires one-off implementation work when a
preference needs a new SQL-backed or search-backed LOV.

Examples:

- `timezone` required custom handling
- `weather_location` needed a dedicated branch and HTTP integration

This creates a mismatch between:

1. the metadata model we introduced
2. the actual execution model in APEX and `orac_code`

## Target State

The target design is:

- `preference_definitions` defines the LOV behaviour
- `orac_code.preference_lov_api` reads the metadata row
- `preference_lov_api` resolves the LOV generically
- page 6 uses one generic select-list path and one generic popup-LOV
  path for standard LOV-backed preferences
- adding a new packaged LOV-backed preference is normally a seed-data
  change only

The preference-definition row should become the source of truth for:

- whether a preference uses an LOV
- what type of LOV it uses
- how the LOV is resolved
- which APEX item family is appropriate

## Design Principles

- Keep `orac_core` as the metadata owner.
- Keep LOV execution inside `orac_code`.
- Do not execute arbitrary SQL directly from APEX.
- Do not allow end users to define executable SQL.
- Treat `lov_query` as packaged metadata, not user-authored code.
- Prefer strict allow-listing and validation over convenience.

## Proposed Execution Model

### 1. Metadata remains in `preference_definitions`

Use the existing columns:

- `control_type`
  - `select_list`
  - `popup_lov`
  - `select_one`
- `lov_type`
  - `static`
  - `sql`
- `lov_query`
- `static_lov_code`

No new table is required for the initial refactor.

### 2. Refactor `orac_code.preference_lov_api`

Replace most hard-coded preference-key branching with generic
resolution logic.

Recommended package responsibilities:

- load the metadata row by `pref_key`
- validate the row is active and editable
- route by `lov_type`
- return JSON rows with a standard shape:
  - `display_value`
  - `return_value`

The package should expose one main entrypoint:

```sql
function get_lov_json(
  p_pref_key      in varchar2,
  p_search        in varchar2 default null,
  p_current_value in varchar2 default null
) return clob;
```

### 3. Support `lov_type = 'static'`

For static LOVs, avoid hard-coding per-preference rules.

Options:

1. map `static_lov_code` to known packaged SQL inside
   `preference_lov_api`
2. introduce a future reference table for static LOV values

Recommended first step:

- keep `static_lov_code`
- centralise code-to-query resolution in one package helper

That still leaves a curated allow-list, but removes preference-key
branching from the main logic.

### 4. Support `lov_type = 'sql'`

For packaged SQL LOVs:

- load `lov_query` from `preference_definitions`
- only execute it when the metadata row is packaged/system-owned
- execute inside `orac_code`
- require the query to return columns aliased as:
  - `d`
  - `r`

The SQL should be executed through controlled dynamic SQL in
`orac_code`, not by APEX directly.

### 5. Search-aware LOV support

For popup-LOV or search-driven preferences, allow the SQL to consume:

- `:APEX$SEARCH`
- current value context when needed

This is especially important for:

- `weather_location`

The resolver should allow current-value replay even when the search term
is empty, so an already-saved selection can still render.

For phase 1, `weather_location` remains a curated packaged path rather
than a generic SQL LOV. Its metadata remains useful for form rendering,
but its execution and page-6 interaction model stay specialised.

## Safety Model

This refactor should not become “run arbitrary SQL from a table”.

Minimum safeguards:

- only execute `lov_query` where the row is packaged/system-managed
- reject rows where `lov_query` is null for `lov_type = 'sql'`
- validate the SQL shape before execution where practical
- document required bind support
- log which preference key and LOV path were used
- raise clear errors for invalid metadata

Optional stronger safeguards:

- add a flag such as `is_packaged` or reuse an existing packaged marker
- prevent direct end-user editing of `lov_query`
- restrict SQL to `select` statements only

## APEX Refactor Scope

Page 6 should remain generic.

After the package refactor:

- `P6_PREF_VALUE_SELECT_LIST` should use one generic LOV
- `P6_PREF_VALUE_POPUP_LOV` should use one generic LOV
- the item selection logic should continue to depend only on:
  - `control_type`
  - `value_type`

APEX should not need special preference-key logic for:

- `timezone`
- `default_llm_id`
- `landing_page_id`

Phase-1 exception:

- `weather_location` keeps its dedicated page-6 search term item,
  selected-location display item, search button, results region, and
  JSON save/load handling
- page 6 must preserve existing `weather_location` behaviour unchanged
  until a richer metadata model exists for search-backed JSON LOVs

## Preferences To Normalise First

These should be moved onto the generic metadata-driven LOV path first:

- `date_format`
- `default_llm_id`
- `landing_page_id`
- `timezone`
- `tts_voice`

## Suggested Implementation Sequence

1. Refactor `preference_lov_api` to load the metadata row.
2. Add a helper for `static_lov_code` resolution.
3. Add a helper for packaged `lov_query` execution.
4. Convert existing hard-coded non-HTTP LOVs to metadata-driven
   execution:
   - `date_format`
   - `default_llm_id`
   - `landing_page_id`
   - `timezone`
   - `tts_voice`
5. Keep `weather_location` as a special packaged path until a richer
   metadata model exists for search-backed JSON preferences.
6. Optionally move `weather_location` onto metadata-driven execution in
   a later phase once page-6 interaction metadata exists.

## Why `weather_location` May Stay Special Longer

`weather_location` differs from the others because it:

- calls an external service
- requires search-aware behaviour
- returns JSON payloads, not simple scalar values
- depends on network ACLs and error handling

So the most practical target state for phase 1 is:

- generic metadata-driven execution for normal SQL/static LOVs
- curated packaged special handling for external-service LOVs

That is still a major improvement over the current key-by-key approach.

## Expected End Result

After this refactor, most new scalar LOV-backed preferences should
require only:

1. a seeded `preference_definitions` row
2. optional supporting reference data

They should not normally require:

- new APEX page-6 logic
- a new preference-specific package branch
- a new one-off patch to the form

## Out Of Scope

This plan does not include:

- redesigning `user_preferences`
- replacing JSON preference storage
- changing the weather plugin contract
- full personality/preference integration work
- moving APEX to direct execution of stored SQL metadata

## Success Criteria

The refactor is successful when:

- page 6 renders LOV-backed preferences from metadata without
  preference-key branches for normal LOVs
- `timezone` works from metadata alone
- packaged SQL LOVs can be introduced through seed data
- `weather_location` remains usable without weakening security or
  changing current page-6 behaviour
