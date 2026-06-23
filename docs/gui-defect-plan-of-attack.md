# GUI Defect Plan Of Attack

## Context

The Orac Display web UI can behave oddly after it has been left running for a
long time. Observed symptoms include:

- the tesseract disappearing and reappearing
- the tesseract rendering in an unexpected colour while the UI still reports
  `idle`
- symptoms sometimes appearing after machine sleep or display recovery
- symptoms also appearing after backend Python components have been restarted
  while the web UI remains open

The current evidence points first at the browser/WebGL display lifecycle rather
than the Python response path. Backend restarts can still be a contributing
factor because they cause WebSocket reconnects and may leave stale display state
until fresh state events arrive.

## Plan

1. Add visible/internal render recovery telemetry.
   - Track recovery count.
   - Track the last recovery reason.
   - Track the last recovery timestamp.
   - Surface the information unobtrusively in the display UI after recovery has
     happened.
   - Continue sending browser diagnostics to the display bridge.

2. Reset visual state on WebSocket reconnect/open.
   - Return to a known safe idle state when the display stream reconnects.
   - Keep transcript/runtime identity data only where doing so is clearly safe.
   - Let fresh `state_changed` events override the fallback state immediately.

3. Make Three.js material state deterministic.
   - Reapply all current-state material colours and opacities on each frame or
     state change.
   - Include edge, connector, cube, light, sparkle, bloom-related, and core
     material state.
   - Avoid relying on prior material state after WebGL recovery.

4. Debounce canvas recovery.
   - Prevent repeated canvas remounts from clustered browser events.
   - Keep one remount per short recovery window unless a distinct hard fault is
     detected.

5. Add a display stream watchdog.
   - Detect when the UI says `Live` but no stream event has arrived for a
     configured interval.
   - Refresh the visual idle state without forcing an unnecessary socket
     reconnect.

## Diagnostics To Watch

- `timer-gap`
- `visibility-resume`
- `bfcache-pageshow`
- `webgl-context-lost`
- `webgl-context-restored`
- WebSocket close/open cycles

## Expected Outcome

The display should no longer drift into a mismatched visual state silently. If a
browser or WebGL recovery happens, the UI should record and show the recovery
reason, making the next occurrence diagnosable from the display itself and from
the browser diagnostics sent to the bridge.
