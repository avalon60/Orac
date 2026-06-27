# Home Assistant

The Home Assistant plugin is a hybrid integration that synchronises Home
Assistant inventory and current state into the plugin-owned `ORAC_HA` schema.
It provides deterministic light, switch, and scene control, read-only area
listings, and on-demand resynchronisation through Orac's managed plugin path.

General plugin installation, policy, and lifecycle rules are documented in
[Plugins](../../../docs/plugins.md). The cache ownership and freshness contract
is documented in
[Home Assistant Data Lifecycle](home-assistant-data-lifecycle.md).

## Current Capability

Supported now:

- startup synchronisation of areas, devices, entities, and current states
- on-demand structural and state resynchronisation
- `turn_on`, `turn_off`, and `toggle` for `light` and `switch` entities
- brightness, colour, and colour-temperature control for supported `light`
  entities using live Home Assistant state
- live on/off, brightness, and colour read-back for supported lights
- scene activation through `scene.turn_on`
- exact Home Assistant area and area-alias targeting
- read-only device, light, switch, and scene listings by area
- read-only temperature and humidity queries from synchronised sensor state
- deterministic temperature comparison, availability, and freshness queries
- persistent read-only aliases, including intentional multi-entity groups
- switch entities described as lamps or lights when light terminology is used
- explicit failure for ambiguous, unknown, unsupported, or unsafe requests
- plugin-router audit persistence and fail-closed mutation routing

Not currently implemented:

- general non-climate state questions such as `Is the desk lamp on?`
- arbitrary Home Assistant service calls
- alias creation or management through voice commands
- control of locks, doors, alarms, climate, covers, fans, scripts,
  automations, or other blocked domains
- whole-home commands such as `Turn off all lights`

## Command Reference

Command matching is deterministic, case-insensitive, and tolerant of terminal
punctuation. An optional `please` prefix and optional `the` article are accepted
where shown below.

### Turn Lights and Switches On or Off

Accepted forms:

```text
[please] turn on/off [the] <target>
[please] switch on/off [the] <target>
[please] turn [the] <target> on/off
[please] switch [the] <target> on/off
[please] on/off [the] <target>
[please] <target> on/off
```

Examples:

```text
Turn on the desk lamp
Switch the desk lamp off
Desk lamp on
Office lights off
On the reading light
```

The terse `<target> on/off` form excludes question-like prefixes, so `Is the
desk lamp on?` is not interpreted as a control command.

### Toggle Lights and Switches

Accepted form:

```text
[please] toggle [the] <target>
```

Examples:

```text
Toggle the desk lamp
Toggle kitchen switch
```

### Activate Scenes

Accepted forms:

```text
[please] activate [the] <target>
[please] enable [the] <target>
turn on scene <target>
```

Examples:

```text
Activate movie night
Enable the reading scene
Turn on scene bedtime
```

Scenes are activated only through the allowlisted `scene.turn_on` service.

### Control an Area

An exact Home Assistant area name or area alias can be used as the target. The
command controls all eligible entities of the requested type in that area.

Examples:

```text
Turn on the office lights
Office lights off
Switch off the kitchen switches
```

`lights` includes native `light` entities and `switch` entities whose synced
names identify them as lamps or lights. Area matching is exact; fuzzy room-name
matching is not used. Whole-home targets remain blocked.

### Rich Light Controls

Accepted forms:

```text
[please] set [the] <light> to <1-100> percent
[please] set [the] <light> brightness to <1-100> percent
[please] turn on [the] <light> at <1-100> percent
[please] turn on [the] <light> to <1-100> percent
[please] dim [the] <light>
[please] brighten [the] <light>
[please] make [the] <light> a bit dimmer/brighter
[please] set/make/turn on [the] <light> to <colour>
[please] set/make/turn on [the] <light> <colour>
[please] set/make/turn on [the] <light> to <colour temperature>
[please] reset [the] <light> to <colour temperature>
[please] make [the] <light> warmer/cooler
```

Supported colour names:

- blue
- cyan
- green
- magenta
- orange
- pink
- purple
- red
- teal
- yellow

Supported colour-temperature presets:

- warm white: 2700 K
- soft white: 3000 K
- normal white / neutral white: 4000 K
- cool white: 5000 K
- daylight: 6500 K
- toasty: 2700 K

Rich light control uses live Home Assistant state for capability validation and
relative adjustments. It only targets `light` entities. Switch-domain lamps
remain limited to on/off. Unsupported colour, brightness, or colour-temperature
requests are refused cleanly when the Home Assistant state does not expose the
required capability.

Effect control is not implemented in this pass.

### Live Light Read-Back

Accepted forms include:

```text
Is [the] <light or lamp> on/off?
What state is [the] <light or lamp> in?
How bright is [the] <light>?
What brightness is [the] <light> set to?
What colour is [the] <light>?
What colour temperature is [the] <light>?
What brightness and colour is [the] <light>?
Are any <area> lights on?
Which <area> lights are on?
Are all <area> lights off?
```

Read-back queries fetch live state from Home Assistant only. They do not use
shadow-table state as current truth. `light` entities may report brightness,
colour, and colour temperature when Home Assistant exposes enough attributes.
`switch`-domain lamps can report only on/off state.

### List Devices in an Area

Accepted forms:

```text
[please] list devices/lights/lamps/switches/scenes in [the] <area>
[please] list [the] <area> devices/lights/lamps/switches/scenes
what devices/lights/lamps/switches/scenes are in [the] <area>
which devices/lights/lamps/switches/scenes are in [the] <area>
```

Examples:

```text
List devices in the office
List living room devices
What devices are in the office?
Which lights are in the kitchen?
List switches in the lounge
List scenes in the cinema
```

Listings use the synchronised read-only resolution view and do not make a Home
Assistant REST call. Results are grouped by Home Assistant device where device
metadata is available. The area name or alias must match exactly.

### List Areas

Accepted forms:

```text
[please] list areas
[please] list all areas
what areas are there?
which rooms do we have?
```

Examples:

```text
List areas
What areas are there?
Which rooms do we have?
```

Area inventory uses the synchronised Home Assistant shadow view only. It does
not call Home Assistant live. If no areas are available in the cache, Orac
returns a clear cached-data failure rather than inventing an answer.

### Query Temperature and Humidity

Supported deterministic forms include:

```text
What's the temperature in the lounge?
What is the landing temperature?
What's the humidity on the landing?
What is the landing humidity?
How humid is the landing?
Is the lounge humid?
What's the temperature and humidity in the lounge?
Which is warmer, the lounge or the landing?
Are any sensors unavailable?
When was the lounge sensor last updated?
```

Sensor queries use the synchronised shadow view only to resolve entities and
areas. They then load the Home Assistant token and fetch each resolved entity
through `GET /api/states/{entity_id}`. They never call a Home Assistant service
or change entity state. If the live read fails, any shadow value is clearly
labelled as cached rather than presented as current.

Sensors are classified primarily from Home Assistant `device_class` metadata
as temperature, humidity, battery, or unknown. Unit metadata and explicit
temperature, humidity, or battery wording provide conservative fallback
classification. Missing or unclear metadata remains unknown rather than being
guessed.

For an area-specific query, the resolver requires exactly one active sensor of
the requested role. Area names and Home Assistant area aliases use the same
exact area resolver as area control and listing.

Default interpretations are:

| Reading | Interpretation |
| --- | --- |
| Humidity below 40% | dry |
| Humidity 40-60% | comfortable |
| Humidity above 60-70% | humid |
| Humidity above 70% | very humid; possible damp concern |
| Temperature below 16°C | cold |
| Temperature 16-18°C | cool |
| Temperature 18-19°C | slightly cool |
| Temperature 19-23°C | comfortable |
| Temperature 23-26°C | warm |
| Temperature above 26°C | hot |

Each sensor question fetches current state directly from Home Assistant's
read-only `/api/states` endpoint. Shadow data supplies stable entity and area
metadata only. If the live endpoint cannot be reached, a shadow value may be
returned only with explicit live-read-failure and cached-data wording. Readings
older than `sensor_stale_hours` are marked as potentially stale. The default is
six hours.

### Resynchronise Home Assistant

Recognised phrases:

```text
Sync devices
Sync Home Assistant devices
Resync devices
Resync Home Assistant
Resync Home Assistant devices
Synchronize devices
Synchronize Home Assistant
Synchronize Home Assistant devices
Synchronise devices
Synchronise Home Assistant
Synchronise Home Assistant devices
Sink devices
```

These commands execute the same approved structural and current-state sync path
used during plugin startup.

## Target Resolution

Control targets are resolved in this order:

1. Enabled persistent aliases.
2. Exact entity ID, object ID, entity name, original name, friendly name, or
   device name.
3. Exact Home Assistant area name or area alias.

Aliases may intentionally map one spoken name to several entities. Ordinary
duplicate names remain ambiguous and are refused. Unsupported child entities
that share a device name, such as power sensors or firmware entities, are
ignored when one valid controllable entity remains.

Persistent aliases are stored in `orac_ha.device_aliases`. They are read-only
to the runtime and are maintained through reviewed DBA SQL or deployment seed
scripts. The plugin does not create aliases automatically and exposes no alias
management voice commands.

## Safety and Confirmation

The plugin permits only these service mappings:

| Domain | Actions | Home Assistant service |
| --- | --- | --- |
| `light` | on, off, toggle | `light.turn_on`, `light.turn_off`, `light.toggle` |
| `switch` | on, off, toggle | `switch.turn_on`, `switch.turn_off`, `switch.toggle` |
| `scene` | activate | `scene.turn_on` |

The plugin refuses:

- whole-home commands
- blocked domains
- unsupported action/domain combinations
- ambiguous targets or areas
- unknown targets or areas
- aliases containing incompatible entity types

Control uses an isolated short-lived Home Assistant REST client and the access
token from Orac's plugin PAT vault. Orac does not fake shadow-state changes. A
success response is returned only when Home Assistant confirms the affected
entity IDs; otherwise the result is explicitly unconfirmed or failed.

## Configure Connection Details

Edit `plugins/home_assistant/plugin.ini` for non-secret values such as protocol,
host, port, TLS verification, and sync behaviour. Do not place the token there.

The plugin manifest defines required settings and secret keys. Unresolved
template placeholders keep the plugin disabled.

## Create a Long-Lived Access Token

Create a Home Assistant long-lived access token with access to the required
inventory, state, and allowlisted service APIs, then store it in Orac's
encrypted plugin PAT vault:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token
```

Inspection commands do not reveal the value:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --list-expected
bin/plugin-pat-mgr.sh --plugin home_assistant --list-keys
bin/plugin-pat-mgr.sh --plugin home_assistant --check access_token
```

Use `--reveal` only for an explicit local diagnostic need. Never put the token
in logs, documentation, shell history, or normal configuration files.

## Database and Synchronisation

Home Assistant data is owned by the plugin schema and deployed through the
plugin database deployment system. Runtime writes use the approved
`orac_ha.ha_sync_api` package. Control resolution and area listings use the
read-only `orac_ha.ha_control_resolution_v` view granted to `ORAC_PLUGIN`.
Temperature/humidity queries use the same view, including device class, unit,
state, and update timestamps.

The service performs its configured startup sync after dependencies and
credentials are available. Missing credentials or an offline Home Assistant
instance degrade the plugin without granting broader database or network
authority.

### Status Surface

The plugin exposes a redacted operational status provider declared in
`plugins/home_assistant.json` as `home_assistant.status_summary`. This is admin
diagnostic metadata, not a conversational capability, and it is not part of
prompt routing or arbitration.

The status summary combines:

- latest structural startup sync time and status from `orac_ha.ha_sync_runs`
- latest state sync time and status from `orac_ha.ha_sync_runs`
- current shadow-table counts for areas, devices, entities, and states
- last redacted sync/runtime error
- runtime service-running and Home Assistant API reachability when available

The APEX-facing source is the read-only
`orac_ha.ha_status_summary_v` view. The Home Assistant service also exposes a
read-only `status` command through Orac's managed plugin service boundary.
React diagnostics can consume the same provider shape when an admin diagnostic
panel is added.

Use this status surface first when Orac cannot find a target such as `the lounge
lamp`. It should show whether Home Assistant was reachable, whether the last
sync failed, whether shadow data is empty, and when Orac last refreshed Home
Assistant inventory and state data.

Check logs for accepted commands, sync results, target refusals, REST failures,
or confirmation failures:

```bash
bin/orac-ctl.sh logs ai
```

## Troubleshooting

### Plugin remains disabled

- Confirm `plugins/home_assistant.json` is enabled.
- Check required `plugin.ini` values for empty or template-placeholder values.
- Confirm the PAT vault contains `access_token`.
- Confirm plugin database deployment completed.

### A target is unknown or ambiguous

- Run `Sync devices` after changing Home Assistant names, areas, or entities.
- Use the exact Home Assistant friendly name, device name, entity ID, area name,
  or configured alias.
- Check for duplicate controllable entities with the same name.
- Add a reviewed persistent alias when a stable spoken name is required.

### Home Assistant is unreachable or control fails

- Verify protocol, host, port, and TLS settings.
- Confirm the token remains valid and can call the required service.
- Check whether certificate verification matches the deployment.
- Review logs for HTTP status, timeout, confirmation, or plugin-scoped errors.

### Area listing is empty

- Confirm entities or devices are assigned to that Home Assistant area.
- Confirm the requested type matches the entities in the area.
- Run `Sync devices` to refresh cached inventory.
- Use the exact area name or one of its Home Assistant aliases.

### A temperature or humidity sensor is missing or ambiguous

- Confirm the entity has the expected Home Assistant `device_class`.
- Confirm the entity or its device is assigned to the requested area.
- Run `Sync devices` after changing Home Assistant metadata.
- If multiple sensors of one role exist in an area, configure a preferred
  sensor before relying on natural-language lookup.
