# Orac Protocol – Release & Versioning Guide

This folder contains the canonical **protocol schema** and **validator** packaged as `orac-protocol`.
Clients (e.g., **Orac-Client**) install it directly from this repo via a **Git tag** (no PyPI).

* Package path: `protocol/` (this folder)
* Schema path: `orac_protocol/resources/json_schema/protocol.schema.json`
* Version file(s):

  * `protocol/pyproject.toml` → `[project].version`
  * `orac_protocol/__init__.py` → `SCHEMA_VERSION`

## Current Wire Contract

The canonical schema is:

```text
protocol/orac_protocol/resources/json_schema/protocol.schema.json
```

Runtime validation must use this schema. Production code must not silently
replace validation with a no-op; the only accepted no-op mode is the explicit
development override controlled by `ORAC_ALLOW_NOOP_PROTOCOL_VALIDATION`.

Orac uses the same newline-delimited JSON envelope for normal responses and
stream events. The required envelope fields are `v`, `type`, `id`, `ts`, and
`route`. Stream frames also include `reply_to`, `meta`, `payload`, and `error`
when emitted by the current runtime.

### Stream Frames

The current stream frame types are:

- `stream_start`
- `text_delta`
- `text_chunk`
- `stream_end`
- `stream_error`
- `stream_cancelled`

`meta.model` is the canonical runtime model identity. Payload-level `model` on
`stream_start` is legacy-compatible only.

`stream_start.payload` currently carries:

- `content_type`: currently `text`
- `voice_session_id`: optional client voice session identifier
- `turn_id`: request/turn identifier used by voice playback handling

`text_delta.payload` is for immediate UI display. The current canonical field is:

- `delta`: the incremental text to append to the visible response

`content_delta` is accepted as a legacy alias by the schema, but the runtime
emits `delta`.

`text_chunk.payload` is for speech-oriented text chunks. The current fields are:

- `chunk`: speech-friendly text chunk
- `session_id`: conversation/session identifier when available
- `voice_session_id`: voice client session identifier when available
- `turn_id`: request/turn identifier

`stream_end.payload` carries:

- `stop_reason`: `stop`, `length`, `tool_call`, or `error`
- `voice_session_id`: optional voice client session identifier
- `turn_id`: optional request/turn identifier
- `usage`: optional token metadata with `prompt_tokens`, `completion_tokens`,
  and `total_tokens`

`stream_error` uses the envelope `error` object for `code` and `message`.
`stream_cancelled.payload.reason` is optional for compatibility; current
barge-in cancellation emits `reason`, `voice_session_id`, and `turn_id`.

### Voice Cancellation

Voice cancellation is a control request on route `orac.voice.cancel`.

Request payload fields:

- `scope`: one of `turn`, `session`, `active`, or `all`
- `reason`: caller-readable cancellation reason
- `session_id`: required for `turn`, `session`, and `active`
- `turn_id`: required for `turn`

Response payload fields:

- `cancelled`: boolean acknowledgement
- `discarded`: number of queued/active voice items discarded

### TTS Playback Frames

The local voice path emits playback lifecycle frames on the same protocol
envelope:

- `tts_playback_started`
- `tts_playback_finished`
- `tts_playback_cancelled`
- `tts_playback_error`
- `voice_turn_complete`

TTS payload fields:

- `turn_id`: voice/request turn identifier
- `request_id`: compatibility copy of the turn/request identifier when emitted
- `timestamp`: event timestamp
- `utterance_id`: optional queued utterance identifier
- `chunk_id`: compatibility copy of `utterance_id` when emitted
- `reason`: optional lifecycle reason or error summary

`tts_playback_error` also carries an envelope `error` object.

### Display Compatibility

`web/orac-display` consumes display bridge events, not raw protocol envelopes.
It supports canonical display events such as `transcript.orac.delta` and
compatibility aliases matching backend frame names: `stream_start`,
`text_delta`, `stream_end`, and `response`.

We use **semantic versioning**:

* **MAJOR**: breaking changes to the wire format
* **MINOR**: backward-compatible additions
* **PATCH**: fixes / clarifications, no API change

---

## 0) Quick checklist (TL;DR)

* [ ] Create a branch from `develop`
* [ ] Update schema + code, bump versions in **both** files
* [ ] Update `CHANGELOG.md`
* [ ] Commit → merge to `develop`
* [ ] Tag: `protocol/vX.Y.Z` on the **merge commit**
* [ ] Push branch + tag
* [ ] Update **Orac-Client** to that tag in `pyproject.toml`
* [ ] `pip install` and sanity-test `validate_frame`
* [ ] (Optional) merge `develop` → `main` to keep main in sync

---

## 1) Make your changes

1. Edit the schema:
   `orac_protocol/resources/json_schema/protocol.schema.json`

2. If you added fields or changed validation logic, update any related code in:
   `orac_protocol/validator.py` (usually unchanged)
   `orac_protocol/__init__.py` (version constant)

3. Bump versions:

   * `protocol/pyproject.toml` → `[project].version = "X.Y.Z"`
   * `orac_protocol/__init__.py` → `SCHEMA_VERSION = "X.Y.Z"`

4. Update `protocol/CHANGELOG.md` with a clear entry:

   * **Added** / **Changed** / **Removed**

---

## 2) Branching model (default branch: `develop`)

### GitKraken

* **Create a feature branch** from `develop`:

  * Right-click `develop` → *Create branch here…* → `feat/protocol-X.Y.Z`
* Make commits.
* **Merge back** into `develop`:

  * Drag `feat/protocol-X.Y.Z` onto `develop` → *Merge into develop*
  * Push `develop`.

### Git CLI

```bash
git switch develop
git pull
git switch -c feat/protocol-X.Y.Z
# … edit files, commit …
git commit -am "protocol: bump to vX.Y.Z; update schema & CHANGELOG"
git switch develop
git merge --no-ff feat/protocol-X.Y.Z
git push origin develop
