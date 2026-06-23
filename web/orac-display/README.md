# Orac Display Web

Thin React display for Orac satellite and desktop views.

The app is designed to behave like an appliance UI:

- standalone browser window support
- kiosk / full-screen support
- reconnecting display stream
- offline / disconnected state
- optional vertical state-button rail

## Transport

The existing `[display].enabled` setting in `resources/config/orac.ini`
must remain `true` to emit live events.

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
bin/orac-web-display.sh
```

3. If you want browser-only mode without the auto-open helper, open:

```text
http://localhost:5173
```

## Launch Styles

### Normal development tab

Run:

```bash
bin/orac-web-display.sh
```

The launcher starts the dev server and opens the browser app window. If you
prefer a plain tab, open `http://localhost:5173` manually.
The launcher also enables the optional transcript panels by default.

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

### Optional transcript panels

The `bin/orac-web-display.sh` launcher enables the current-turn transcript
panels automatically.

If you run Vite manually, set:

```bash
VITE_ORAC_SHOW_TRANSCRIPT_PANELS=true npm run dev
```

The panels are off by default in production-style builds. When enabled, the
display shows the latest recognised user utterance on the left and Orac's
current response on the right.

Supported transcript events:

- `runtime.identity`
- `transcript.turn.clear`
- `transcript.user.final`
- `transcript.orac.start`
- `transcript.orac.delta`
- `transcript.orac.final`

Consumed payload fields:

- transcript text is read from `text`, `message`, `delta`, `chunk`, or
  `content`
- runtime identity is read from `model`, `persona`, `personality_code`, and
  `personality_name`
- runtime identity source is read from `llm_source`
- state updates read `state` and optional `message`
- UI configuration reads `buttons_visible` and `show_transcript_panels`

The display also accepts the current compatibility aliases used by the local
voice path and older bridge payloads:

- `voice_stt_final`
- `stt_final`
- `stream_start`
- `text_delta`
- `stream_end`
- `response`

## Notes

- The React UI remains a thin display/control surface.
- Browser mode starts the Node bridge and mirrors the existing display
  payloads to the browser.
- Browser WebSocket connect/reconnect/disconnect logs are quiet by default.
  Set `ORAC_DISPLAY_LOG_BROWSER_CONNECTIONS=true` when diagnosing browser
  display transport reconnects.
