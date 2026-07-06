# Orac Atom Display

The atom display is a local visual companion for Orac. It is not
started as part of the backend stack by default.

## Configuration

Display event emission is controlled by `resources/config/orac.ini`:

```ini
[display]
enabled = false
auto_start = false
host = 127.0.0.1
port = 8766
state_file = ${ORAC_HOME}/var/tmp/orac_display_state.json
connect_timeout_seconds = 0.05
```

Set `enabled = true` to have the voice loop emit best-effort display state
events. If the display is not running, Orac continues normally and writes the
latest display state file for startup recovery.

## Launching

Run the display in the foreground:

```bash
bin/orac-display.sh
```

Run it as a companion process:

```bash
bin/orac-display.sh start --mode compact
bin/orac-display.sh status
bin/orac-display.sh stop
```

The same commands are available through `orac-ctl.sh`:

```bash
bin/orac-ctl.sh display start --mode compact
bin/orac-ctl.sh display status
bin/orac-ctl.sh display stop
```

`orac-ctl.sh start` does not launch the display. This keeps headless and server
use cases separate from the desktop UI.

## Event Schema

The display receives newline-delimited JSON over localhost. The current primary
event is:

```json
{
  "v": 1,
  "event": "state_changed",
  "state": "listening",
  "message": "Listening for wake word",
  "session_id": "local-voice-session-example",
  "turn_id": "req-example",
  "created_on": "2026-05-08T18:00:00+00:00"
}
```

Supported states are:

- `idle`
- `initialising`
- `listening`
- `thinking`
- `speaking`
- `interrupted`
- `error`
- `sleeping`
- `shutdown`

The display remains a visual endpoint only. Orac business logic should continue
to live in the runtime and voice modules.
