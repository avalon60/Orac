# Orac Display Web

Thin React display for Orac satellite and desktop views.

The app is designed to behave like an appliance UI:

- standalone browser window support
- kiosk / full-screen support
- reconnecting display stream
- offline / disconnected state
- optional vertical state-button rail

## Transport Options

The display payload schema stays the same in both modes.
The existing `[display].enabled` setting in `resources/config/orac.ini`
must remain `true` for either mode to emit live events.

### Preferred Python mode

The Python Orac runtime now owns the browser WebSocket transport.

1. Start the Orac voice runtime with browser mode enabled:

```bash
python bin/voice_ai.py --browser-mode
```

To show the side-panel state buttons, add `--buttons`:

```bash
python bin/voice_ai.py --browser-mode --buttons
```

2. Start the React dev server:

```bash
bin/orac-display-web.sh
```

3. If you want browser-only mode without the auto-open helper, open:

```text
http://localhost:5173
```

### Temporary bridge mode

The old Node bridge is still available for compatibility, but it is
deprecated and should be treated as temporary.

1. Start the bridge:

```bash
cd web/orac-display
node bridge.js
```

2. Start the Orac voice runtime:

```bash
python bin/voice_ai.py
```

3. Start the React dev server:

```bash
bin/orac-display-web.sh
```

4. Open the app:

```text
http://localhost:5173
```

## Launch Styles

### Normal development tab

Run:

```bash
bin/orac-display-web.sh
```

The launcher starts the dev server and opens the browser app window. If you
prefer a plain tab, open `http://localhost:5173` manually.

### App-style window

Use Chromium or Chrome app mode if you want to open an already-running Vite
server manually:

```bash
chromium --app=http://localhost:5173
```

### Kiosk / full-screen satellite display

Use kiosk mode for a dedicated display surface:

```bash
chromium --kiosk http://localhost:5173
```

## Browser Configuration

Set the browser WebSocket endpoint with an environment variable if needed:

```bash
VITE_ORAC_DISPLAY_WS_URL=ws://127.0.0.1:8767
```

The default already targets `ws://127.0.0.1:8767`.

## Notes

- The React UI remains a thin display/control surface.
- Browser mode is owned by Python and mirrors the existing display payloads.
- The Node bridge remains for transition only.
