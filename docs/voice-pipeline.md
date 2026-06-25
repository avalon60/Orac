# Voice Pipeline

The local voice pipeline covers activation, microphone capture, speech-to-text,
Orac request streaming, text-to-speech, playback, interruption, and display
events.

## Runtime Flow

1. Wait for manual or wake-word activation.
2. Capture microphone audio using fixed-duration or VAD recording.
3. Transcribe locally with Faster Whisper.
4. Send the recognised prompt to the Orac protocol service.
5. Stream response text and speech chunks.
6. Synthesize with Kokoro or Piper.
7. Play the response and return to wake listening.

The detailed state and event contract is documented in
[Voice Turn Lifecycle](voice-turn-lifecycle.md).

## Install Voice Dependencies

Core voice dependencies are part of the project. For openWakeWord support:

```bash
poetry install --no-root -E voice-wake-openwakeword
```

Linux microphone capture may require the system PortAudio development/runtime
packages, such as `portaudio19-dev`.

## Activation

openWakeWord is the recommended local backend:

```ini
[voice]
activation_mode = openwakeword
wake_engine = openwakeword
openwakeword_model_names = hey_orac
openwakeword_threshold = 0.75
openwakeword_inference_framework = auto
wake_rearm_seconds = 0.2
openwakeword_refractory_seconds = 0.2
```

Packaged models live under
`${ORAC_HOME}/resources/models/wakeword/openwakeword`. Local models should use
`${ORAC_HOME}/var/models/wakeword/openwakeword` or another directory listed in
`openwakeword_model_dirs`.

Set `activation_mode = enter` for manual activation. `stt_phrase` is a
diagnostic fallback, not a production wake-word detector.

Porcupine is optional and requires a Picovoice access key:

```bash
poetry install --no-root -E voice-wake-porcupine
PYTHONPATH=src poetry run python -m lib.api_key_store --set picovoice/access_key
```

Store the key in the encrypted API key store, never in `orac.ini`.

## Speech-to-Text

Faster Whisper is the supported local STT engine. The shipped configuration uses
the CPU and an `int8` compute type:

```ini
[voice]
stt_engine = faster_whisper
stt_model = small.en
stt_device = cpu
stt_compute_type = int8
stt_record_mode = vad
```

Recording and VAD thresholds control maximum recording time, speech start/end,
padding, silence, and initial timeout. Tune them for the microphone and room;
do not assume one threshold set is portable across devices.

## Text-to-Speech

Runtime user preferences for speech are provider-neutral hints. See
[Runtime User Preferences](user_preferences.md) for precedence, validation, and
the complete preference matrix.

| Engine | `tts_voice` | `tts_rate` | `tts_pitch` |
|---|---|---|---|
| Kokoro | Maps to Kokoro `voice` selection. | Mapped to OpenAI-compatible speech `speed`. | Unsupported; debug-logged and ignored. |
| Piper | Maps to Piper voice/model path selection. | Unsupported; debug-logged and ignored. | Unsupported; debug-logged and ignored. |

Only Kokoro and Piper are currently implemented local TTS engines. Voice
catalogue provider fields are extension points, not evidence that another TTS
provider is available.

### Kokoro

Kokoro is the shipped primary TTS backend. Orac expects a local
OpenAI-compatible speech endpoint and can manage the Compose `voice` profile.

```ini
[voice]
tts_engine = kokoro
tts_fallback_engine = piper
tts_kokoro_autostart = true
tts_kokoro_runtime = docker-cpu
tts_kokoro_base_url = http://127.0.0.1:8880/v1
tts_kokoro_model = kokoro
tts_kokoro_voice = bm_george
tts_kokoro_response_format = wav
```

Supported runtime modes are:

- `docker-cpu`: manage the CPU image through Compose
- `docker-gpu`: use the GPU image and Docker NVIDIA runtime
- `external`: connect to an already managed service

Verify the endpoint directly:

```bash
curl -sS \
  -H 'Content-Type: application/json' \
  -o /tmp/orac-kokoro-test.wav \
  -X POST http://127.0.0.1:8880/v1/audio/speech \
  -d '{"model":"kokoro","voice":"af_heart","input":"Kokoro is available for Orac.","response_format":"wav"}'
file /tmp/orac-kokoro-test.wav
```

The base URL may include or omit `/v1` and a trailing slash. Orac normalises it
to the speech endpoint.

Resolved `tts_rate` is sent to Kokoro as the OpenAI-compatible `speed` field.
Resolved `tts_pitch` is not supported by the current Kokoro adapter; it is
debug-logged and ignored.

### Piper

Piper is the lightweight local fallback. Voice assets default to:

```ini
[voice]
tts_fallback_engine = piper
tts_voice = en_GB-alba-medium
tts_voice_dir = ${ORAC_HOME}/var/models/piper
```

Orac also packages an `en_GB-alba-medium` fallback under
`${ORAC_HOME}/resources/models/piper`.

Resolved `tts_voice` selects the Piper voice/model path. The current Piper
adapter does not support per-turn `tts_rate` or `tts_pitch`; both options are
debug-logged and ignored safely.

## Playback, Barge-In, and AEC

The shipped playback backend is `shell`. Native PCM playback is experimental
and is required for reverse-frame acoustic echo cancellation.

Barge-in is experimental and disabled by default. The runtime emits explicit
playback-started, finished, cancelled, and error events; these events define
when interruption monitoring is active.

Wake-word interruption is safer than VAD-only interruption because an
open-speaker microphone may hear Orac's own response. VAD-only mode should be
treated as diagnostic unless echo cancellation or suitable hardware is in use.

The `livekit` AEC backend requires the `voice-aec-livekit` extra and native
playback. See [Acoustic Echo Cancellation Design](aec-design.md).

## Run a Voice Session

```bash
PYTHONPATH=src poetry run python -m orac_voice.voice_loop_local \
  --voice-session \
  --activation-mode openwakeword
```

For display/browser launch behavior, see
[`web/orac-display/README.md`](../web/orac-display/README.md).
